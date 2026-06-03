data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  # /20 subnets carved from the VPC CIDR, one per AZ.
  # Private subnets occupy the lower half (offsets 0..az_count-1).
  # Public subnets occupy a higher offset block when enabled.
  private_subnet_cidrs = [
    for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, i)
  ]

  public_subnet_cidrs = var.create_public_subnets ? [
    for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, 8 + i)
  ] : []
}

resource "aws_vpc" "this" {
  #checkov:skip=CKV2_AWS_12:Default SG is unused — all resources attach to purpose-built SGs. Restricting it is not load-bearing here.
  #checkov:skip=CKV2_AWS_11:VPC flow logs are out of scope for the sample (additional CloudWatch/S3 cost and IAM plumbing).
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.name_prefix}-vpc"
  }
}

resource "aws_subnet" "private" {
  count = var.az_count

  vpc_id            = aws_vpc.this.id
  cidr_block        = local.private_subnet_cidrs[count.index]
  availability_zone = local.azs[count.index]

  tags = {
    Name = "${var.name_prefix}-private-${local.azs[count.index]}"
    Tier = "private"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.name_prefix}-private-rt"
  }
}

resource "aws_route_table_association" "private" {
  count = var.az_count

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# Shared security group for all interface VPC endpoints. Allows HTTPS in from
# anything in the VPC; everything that needs to reach an AWS service via an
# endpoint just needs to be inside this VPC.
resource "aws_security_group" "vpc_endpoints" {
  #checkov:skip=CKV_AWS_382:VPCE SG egress is response-only; AWS service traffic stays inside the VPC.
  name_prefix = "${var.name_prefix}-vpce-"
  description = "Allow HTTPS from within the VPC to interface VPC endpoints."
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.this.cidr_block]
  }

  egress {
    description = "Outbound (AWS service responses)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-vpce"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Interface endpoints — DNS resolution for the AWS service hostname is
# automatic when private_dns_enabled = true.
locals {
  interface_endpoints = {
    ecr_api        = "ecr.api"
    ecr_dkr        = "ecr.dkr"
    secretsmanager = "secretsmanager" # pragma: allowlist secret
    logs           = "logs"
    ssm            = "ssm"
    ssmmessages    = "ssmmessages"
    ec2messages    = "ec2messages"
  }
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_endpoints

  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${var.name_prefix}-vpce-${each.key}"
  }
}

# S3 is a gateway endpoint (route-table attachment, free). Required because
# ECR image layers are stored in S3.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = {
    Name = "${var.name_prefix}-vpce-s3"
  }
}

# --------------------------------------------------------------------------
# Optional public subnets + Internet Gateway.
# Used during JWT integration testing when the ALB needs to be reachable
# from the public internet. Set create_public_subnets = true to enable.
# --------------------------------------------------------------------------

resource "aws_internet_gateway" "this" {
  count = var.create_public_subnets ? 1 : 0

  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.name_prefix}-igw"
  }
}

resource "aws_subnet" "public" {
  count = var.create_public_subnets ? var.az_count : 0

  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.public_subnet_cidrs[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.name_prefix}-public-${local.azs[count.index]}"
    Tier = "public"
  }
}

resource "aws_route_table" "public" {
  count = var.create_public_subnets ? 1 : 0

  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this[0].id
  }

  tags = {
    Name = "${var.name_prefix}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count = var.create_public_subnets ? var.az_count : 0

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}
