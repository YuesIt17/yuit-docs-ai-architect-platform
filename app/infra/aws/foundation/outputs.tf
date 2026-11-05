output "region" {
  description = "AWS region."
  value       = var.region
}

output "terraform_state_bucket" {
  description = "Bucket that stores Terraform state."
  value       = module.terraform_state_bucket.name
}

output "data_bucket" {
  description = "Bucket for platform files."
  value       = module.data_bucket.name
}

output "observability_bucket" {
  description = "Bucket for Loki and Tempo data."
  value       = module.observability_bucket.name
}

output "backups_bucket" {
  description = "Bucket for database backups."
  value       = module.backups_bucket.name
}

output "vault_unseal_kms_alias" {
  description = "KMS alias for Vault auto-unseal."
  value       = aws_kms_alias.vault_unseal.name
}

output "ecr_repository_urls" {
  description = "Image repository URLs by name."
  value       = { for name, repository in aws_ecr_repository.this : name => repository.repository_url }
}
