resource "aws_security_group" "alb" {
  #checkov:skip=CKV_AWS_382:Open egress is acceptable in this sample; the ALB only ever forwards to the app SG, but tightening to the app SG would couple resource ordering across modules.
  name_prefix = "${var.name_prefix}-alb-"
  description = "ALB for ${var.name_prefix} (internal or internet-facing depending on alb_internet_facing var)."
  vpc_id      = var.vpc_id

  egress {
    description = "Outbound to app tasks"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-alb"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Inbound 443 from the configured CIDR list. Only used when the ALB is
# internet-facing — for internal ALBs, callers (Gateway VPCE, etc.) attach
# ingress rules referencing this SG.
resource "aws_security_group_rule" "alb_public_https" {
  count = var.alb_internet_facing && length(var.alb_ingress_cidrs) > 0 ? 1 : 0

  type              = "ingress"
  description       = "HTTPS from configured public CIDRs"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = var.alb_ingress_cidrs
  security_group_id = aws_security_group.alb.id
}

# SG attached to ECS tasks. Accepts traffic only from the ALB SG.
resource "aws_security_group" "app" {
  #checkov:skip=CKV_AWS_382:Open egress is acceptable in this sample; egress traffic is naturally constrained to in-VPC AWS services via VPCE + RDS.
  name_prefix = "${var.name_prefix}-app-"
  description = "ECS app tasks for ${var.name_prefix}."
  vpc_id      = var.vpc_id

  egress {
    description = "All outbound (DB, Secrets Manager, ECR, Logs via VPCE)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-app"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "alb_to_app" {
  type                     = "ingress"
  description              = "ALB to app on container port"
  from_port                = var.container_port
  to_port                  = var.container_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.alb.id
}

# App tasks reach Postgres. Owned here (not in data module) to avoid cycles.
resource "aws_security_group_rule" "app_to_db" {
  type                     = "ingress"
  description              = "App to Postgres"
  from_port                = var.db_port
  to_port                  = var.db_port
  protocol                 = "tcp"
  security_group_id        = var.db_security_group_id
  source_security_group_id = aws_security_group.app.id
}
