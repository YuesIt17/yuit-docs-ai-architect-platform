data "aws_availability_zones" "available" {
  state = "available"

  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  name = "${var.project}-${var.environment}"

  # EKS requires subnets in at least two availability zones.
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

module "vpc" {
  #checkov:skip=CKV_TF_1:Registry module pinned to an exact version, which is easier to review and upgrade than a commit hash.
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.7.3"

  name = local.name
  cidr = var.vpc_cidr
  azs  = local.azs

  public_subnets  = [for index, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, index)]
  private_subnets = [for index, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, index + 1)]

  # One NAT gateway is a single point of failure, which is acceptable for a lab and saves about $35 a month.
  enable_nat_gateway = true
  single_nat_gateway = true

  enable_dns_hostnames = true
  enable_dns_support   = true

  # The AWS Load Balancer Controller finds subnets through these tags.
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}

# Free gateway endpoint: S3 traffic skips the NAT gateway and its per-GB charge.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids

  tags = {
    Name = "${local.name}-s3"
  }
}
