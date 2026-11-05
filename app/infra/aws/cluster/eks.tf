locals {
  node_block_device_mappings = {
    xvda = {
      device_name = "/dev/xvda"
      ebs = {
        volume_size           = var.node_disk_size_gb
        volume_type           = "gp3"
        encrypted             = true
        delete_on_termination = true
      }
    }
  }

  # IMDSv2 only, with a hop limit that stops pods from reading the node's IAM credentials.
  node_metadata_options = {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
}

module "eks" {
  #checkov:skip=CKV_TF_1:Registry module pinned to an exact version, which is easier to review and upgrade than a commit hash.
  source  = "terraform-aws-modules/eks/aws"
  version = "21.29.0"

  name               = local.name
  kubernetes_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  endpoint_private_access      = true
  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.api_public_access_cidrs

  authentication_mode                      = "API"
  enable_cluster_creator_admin_permissions = true
  enable_irsa                              = true

  # EKS already applies envelope encryption with an AWS-owned key. A customer key would add a monthly fee.
  create_kms_key    = false
  encryption_config = null

  enabled_log_types                      = ["audit", "authenticator"]
  cloudwatch_log_group_retention_in_days = var.log_retention_days

  addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni = {
      before_compute = true
      # Docker Desktop cannot enforce the chart's NetworkPolicy objects. This setting makes EKS enforce them.
      configuration_values = jsonencode({
        enableNetworkPolicy = "true"
      })
    }
  }

  eks_managed_node_groups = {
    general = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = [var.general_instance_type]

      min_size     = var.general_node_count
      max_size     = var.general_node_count
      desired_size = var.general_node_count

      block_device_mappings = local.node_block_device_mappings
      metadata_options      = local.node_metadata_options
      labels = {
        workload = "general"
      }
    }

    ollama = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = [var.ollama_instance_type]

      min_size     = var.ollama_node_count
      max_size     = max(var.ollama_node_count, 1)
      desired_size = var.ollama_node_count

      block_device_mappings = local.node_block_device_mappings
      metadata_options      = local.node_metadata_options
      labels = {
        workload = "ollama"
      }

      # Only pods that tolerate this taint can run here, which keeps the node free for inference.
      taints = {
        dedicated = {
          key    = "dedicated"
          value  = "ollama"
          effect = "NO_SCHEDULE"
        }
      }
    }
  }
}

# Managed outside the module, because its IAM role needs the cluster's OIDC provider first.
resource "aws_eks_addon" "ebs_csi" {
  cluster_name             = module.eks.cluster_name
  addon_name               = "aws-ebs-csi-driver"
  service_account_role_arn = module.ebs_csi_role.arn

  depends_on = [module.eks]
}
