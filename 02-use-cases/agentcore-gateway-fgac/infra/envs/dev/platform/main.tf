locals {
  name_prefix = "${var.project_name}-dev"
}

module "network" {
  source                = "../../../modules/network"
  name_prefix           = local.name_prefix
  create_public_subnets = var.alb_internet_facing
}

module "data" {
  source      = "../../../modules/data"
  name_prefix = local.name_prefix
  vpc_id      = module.network.vpc_id
  vpc_cidr    = module.network.vpc_cidr
  subnet_ids  = module.network.private_subnet_ids
}

module "compute" {
  source = "../../../modules/compute"

  name_prefix        = local.name_prefix
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids

  alb_subnet_ids      = var.alb_internet_facing ? module.network.public_subnet_ids : module.network.private_subnet_ids
  alb_internet_facing = var.alb_internet_facing
  alb_ingress_cidrs   = var.alb_ingress_cidrs

  db_address           = module.data.db_address
  db_port              = module.data.db_port
  db_name              = module.data.db_name
  db_master_secret_arn = module.data.master_user_secret_arn
  db_security_group_id = module.data.security_group_id

  okta_issuer   = var.okta_issuer
  okta_audience = var.okta_audience
  okta_jwks_uri = var.okta_jwks_uri

  route53_zone_id = var.route53_zone_id
  alb_fqdn        = var.alb_fqdn

  container_image = var.container_image
}
