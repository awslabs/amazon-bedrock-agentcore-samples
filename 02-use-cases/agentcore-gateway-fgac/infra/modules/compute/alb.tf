resource "aws_lb" "internal" {
  #checkov:skip=CKV_AWS_91:ALB access logging requires an S3 logging bucket; omitted for sample simplicity.
  #checkov:skip=CKV_AWS_150:Deletion protection is intentionally off so `terraform destroy` works cleanly in the demo.
  #checkov:skip=CKV2_AWS_28:WAF is out of scope for this sample; auth is enforced by ALB jwt-validation + downstream checks.
  name               = "${var.name_prefix}-alb"
  internal           = !var.alb_internet_facing
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.alb_subnet_ids

  drop_invalid_header_fields = true

  tags = {
    Name = "${var.name_prefix}-alb"
  }
}

resource "aws_lb_target_group" "app" {
  name        = "${var.name_prefix}-app-tg"
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 15

  tags = {
    Name = "${var.name_prefix}-app-tg"
  }
}

# HTTPS listener. Default action validates the inbound JWT against Okta
# (signature, issuer, audience, role ∈ {customer, admin}) and forwards to
# the app target group on success. ALB rejects invalid tokens before they
# reach the target.
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.internal.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  # Reference the validated cert resource so the listener depends on the
  # DNS validation having completed.
  certificate_arn = aws_acm_certificate_validation.alb.certificate_arn

  default_action {
    type  = "jwt-validation"
    order = 1

    jwt_validation {
      issuer        = var.okta_issuer
      jwks_endpoint = var.okta_jwks_uri

      additional_claim {
        format = "single-string"
        name   = "aud"
        values = [var.okta_audience]
      }
      # Role allowlist is enforced downstream (AgentCore Policy + FastAPI),
      # not at the ALB. ALB's `additional_claim` requires `string-array`
      # for multi-value matches, but the demo's `role` claim is a scalar
      # by design (see README "Token contract" section). Verifying the
      # signature, iss, aud, and expiry here is the meaningful boundary.
    }
  }

  default_action {
    type             = "forward"
    order            = 2
    target_group_arn = aws_lb_target_group.app.arn
  }
}
