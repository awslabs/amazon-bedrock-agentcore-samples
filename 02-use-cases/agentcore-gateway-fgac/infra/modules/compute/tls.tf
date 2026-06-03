# Publicly-trusted ACM certificate for the ALB.
#
# AgentCore Gateway calls the ALB over HTTPS as an out-of-band managed
# service; it uses the standard public CA trust store and cannot import
# custom CAs or skip verification. So the cert must chain to a public
# root, which means: real domain, DNS-validated ACM cert, Route53 alias
# pointing the FQDN at the ALB.

resource "aws_acm_certificate" "alb" {
  domain_name       = var.alb_fqdn
  validation_method = "DNS"

  tags = {
    Name = "${var.name_prefix}-alb"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.alb.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id         = var.route53_zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "alb" {
  certificate_arn         = aws_acm_certificate.alb.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

resource "aws_route53_record" "alb_alias" {
  zone_id = var.route53_zone_id
  name    = var.alb_fqdn
  type    = "A"

  alias {
    name                   = aws_lb.internal.dns_name
    zone_id                = aws_lb.internal.zone_id
    evaluate_target_health = false
  }
}
