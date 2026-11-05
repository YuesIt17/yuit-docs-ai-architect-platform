# Long-lived resources that survive `terraform destroy` of the cluster layer.

data "aws_caller_identity" "current" {}

locals {
  # S3 names are global, so the account ID keeps them unique without committing it to the repository.
  bucket_prefix = "${var.project}-${data.aws_caller_identity.current.account_id}"
}

module "terraform_state_bucket" {
  source = "../modules/secure-bucket"

  name                    = "${local.bucket_prefix}-tfstate"
  noncurrent_version_days = 90
}

module "data_bucket" {
  source = "../modules/secure-bucket"

  name = "${local.bucket_prefix}-data"
}

module "observability_bucket" {
  source = "../modules/secure-bucket"

  name = "${local.bucket_prefix}-observability"

  # Loki and Tempo rewrite objects often, so old versions are dropped quickly to limit cost.
  noncurrent_version_days = 1
  expiration_days         = var.observability_retention_days
}

# Backups have no expiry: a lab can sit deleted for months and still needs its last backup.
module "backups_bucket" {
  source = "../modules/secure-bucket"

  name = "${local.bucket_prefix}-backups"
}

# Vault auto-unseal key. It outlives the cluster because restoring a Vault snapshot needs the same key.
data "aws_iam_policy_document" "vault_unseal_key" {
  #checkov:skip=CKV_AWS_356:In a KMS key policy, the resource "*" means only this key.
  #checkov:skip=CKV_AWS_111:In a KMS key policy, the resource "*" means only this key.
  #checkov:skip=CKV_AWS_109:This is the AWS default key policy, which delegates key access to IAM in this account.
  statement {
    sid       = "AccountAdministersKeyThroughIam"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
}

resource "aws_kms_key" "vault_unseal" {
  description             = "Vault auto-unseal key for ${var.project}-${var.environment}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.vault_unseal_key.json

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_kms_alias" "vault_unseal" {
  name          = "alias/${var.project}-${var.environment}-vault-unseal"
  target_key_id = aws_kms_key.vault_unseal.key_id
}

resource "aws_ecr_repository" "this" {
  #checkov:skip=CKV_AWS_136:AES256 is used because a customer KMS key costs extra and adds no value for one user.
  for_each = var.ecr_repositories

  name                 = each.key
  image_tag_mutability = "IMMUTABLE"

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only the newest images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.ecr_images_to_keep
      }
      action = {
        type = "expire"
      }
    }]
  })
}
