resource "aws_db_subnet_group" "this" {
  name        = "${var.name_prefix}-db"
  description = "Private subnet group for ${var.name_prefix} RDS."
  subnet_ids  = var.subnet_ids

  tags = {
    Name = "${var.name_prefix}-db-subnets"
  }
}

resource "aws_security_group" "db" {
  #checkov:skip=CKV_AWS_382:RDS egress is response-only; tightening this is not load-bearing for sample security posture.
  name_prefix = "${var.name_prefix}-db-"
  description = "Postgres ingress from app tier only."
  vpc_id      = var.vpc_id

  # No ingress rules defined here — callers (compute module) add a rule
  # granting their app SG access via aws_security_group_rule, so we don't
  # depend on the app SG existing at this module's apply time.

  egress {
    description = "Outbound (responses)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-db"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "this" {
  #checkov:skip=CKV_AWS_293:Deletion protection is intentionally off so `terraform destroy` works cleanly in the demo.
  #checkov:skip=CKV_AWS_226:Auto minor version upgrades are out of scope for an ephemeral sample DB.
  #checkov:skip=CKV_AWS_129:RDS log exports (postgresql/upgrade) are out of scope for this sample.
  #checkov:skip=CKV_AWS_161:IAM database authentication is out of scope; the sample uses the AWS-managed master secret.
  #checkov:skip=CKV_AWS_157:Multi-AZ doubles RDS cost and is unnecessary for a single-AZ demo.
  #checkov:skip=CKV_AWS_118:Enhanced monitoring requires an extra IAM role and incurs CloudWatch cost; out of scope for the demo.
  #checkov:skip=CKV_AWS_353:Performance Insights incurs additional cost; not required for the demo.
  #checkov:skip=CKV2_AWS_60:copy_tags_to_snapshot is not load-bearing for a sample with `skip_final_snapshot = true`.
  #checkov:skip=CKV2_AWS_30:Postgres query logging requires a custom parameter group; out of scope for this sample.
  identifier     = "${var.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.db_name
  username = var.db_username

  # AWS manages and rotates the master password in Secrets Manager.
  # The password never enters Terraform state.
  manage_master_user_password = true

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.allocated_storage_gb * 2
  storage_type          = "gp3"
  storage_encrypted     = true

  multi_az               = false
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  port                   = 5432

  backup_retention_period = 7
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  tags = {
    Name = "${var.name_prefix}-postgres"
  }
}
