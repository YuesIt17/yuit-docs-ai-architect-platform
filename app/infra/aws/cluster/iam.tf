# Roles that pods assume through IRSA, so no long-lived AWS keys are stored in the cluster.
# The GitLab runner and database backup roles are added in the phases that introduce those workloads.

data "aws_caller_identity" "current" {}

locals {
  bucket_prefix = "${var.project}-${data.aws_caller_identity.current.account_id}"
}

# These lookups fail early if the foundation layer has not been applied.
data "aws_s3_bucket" "data" {
  bucket = "${local.bucket_prefix}-data"
}

data "aws_s3_bucket" "observability" {
  bucket = "${local.bucket_prefix}-observability"
}

data "aws_s3_bucket" "backups" {
  bucket = "${local.bucket_prefix}-backups"
}

data "aws_kms_key" "vault_unseal" {
  key_id = "alias/${local.name}-vault-unseal"
}

module "ebs_csi_role" {
  #checkov:skip=CKV_TF_1:Registry module pinned to an exact version, which is easier to review and upgrade than a commit hash.
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts"
  version = "6.8.2"

  name                  = "${local.name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    this = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}

module "load_balancer_controller_role" {
  #checkov:skip=CKV_TF_1:Registry module pinned to an exact version, which is easier to review and upgrade than a commit hash.
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts"
  version = "6.8.2"

  name                                   = "${local.name}-load-balancer-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    this = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
}

data "aws_iam_policy_document" "platform_s3" {
  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [data.aws_s3_bucket.data.arn]
  }

  statement {
    sid       = "ReadWriteObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${data.aws_s3_bucket.data.arn}/*"]
  }
}

resource "aws_iam_policy" "platform_s3" {
  name   = "${local.name}-platform-s3"
  policy = data.aws_iam_policy_document.platform_s3.json
}

module "platform_role" {
  #checkov:skip=CKV_TF_1:Registry module pinned to an exact version, which is easier to review and upgrade than a commit hash.
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts"
  version = "6.8.2"

  name = "${local.name}-platform"
  policies = {
    s3 = aws_iam_policy.platform_s3.arn
  }

  oidc_providers = {
    this = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kp:api", "kp:worker"]
    }
  }
}

data "aws_iam_policy_document" "vault" {
  statement {
    sid       = "AutoUnseal"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:DescribeKey"]
    resources = [data.aws_kms_key.vault_unseal.arn]
  }

  statement {
    sid       = "ListSnapshots"
    actions   = ["s3:ListBucket"]
    resources = [data.aws_s3_bucket.backups.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["vault/*"]
    }
  }

  statement {
    sid       = "ReadWriteSnapshots"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${data.aws_s3_bucket.backups.arn}/vault/*"]
  }
}

resource "aws_iam_policy" "vault" {
  name   = "${local.name}-vault"
  policy = data.aws_iam_policy_document.vault.json
}

module "vault_role" {
  #checkov:skip=CKV_TF_1:Registry module pinned to an exact version, which is easier to review and upgrade than a commit hash.
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts"
  version = "6.8.2"

  name = "${local.name}-vault"
  policies = {
    vault = aws_iam_policy.vault.arn
  }

  oidc_providers = {
    this = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["vault:vault"]
    }
  }
}

data "aws_iam_policy_document" "observability_s3" {
  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [data.aws_s3_bucket.observability.arn]
  }

  statement {
    sid = "ReadWriteObjects"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObjectTagging",
      "s3:PutObjectTagging",
    ]
    resources = ["${data.aws_s3_bucket.observability.arn}/*"]
  }
}

resource "aws_iam_policy" "observability_s3" {
  name   = "${local.name}-observability-s3"
  policy = data.aws_iam_policy_document.observability_s3.json
}

module "observability_role" {
  #checkov:skip=CKV_TF_1:Registry module pinned to an exact version, which is easier to review and upgrade than a commit hash.
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts"
  version = "6.8.2"

  name = "${local.name}-observability"
  policies = {
    s3 = aws_iam_policy.observability_s3.arn
  }

  oidc_providers = {
    this = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["observability:loki", "observability:tempo"]
    }
  }
}
