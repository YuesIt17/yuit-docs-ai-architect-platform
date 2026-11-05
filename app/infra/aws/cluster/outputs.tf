output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "kubeconfig_command" {
  description = "Command that connects kubectl to the cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "vpc_id" {
  description = "VPC ID, needed by the AWS Load Balancer Controller."
  value       = module.vpc.vpc_id
}

output "load_balancer_controller_role_arn" {
  description = "IAM role for the AWS Load Balancer Controller."
  value       = module.load_balancer_controller_role.arn
}

output "platform_role_arn" {
  description = "IAM role for the API and worker service accounts."
  value       = module.platform_role.arn
}

output "vault_role_arn" {
  description = "IAM role for the Vault service account."
  value       = module.vault_role.arn
}

output "observability_role_arn" {
  description = "IAM role for the Loki and Tempo service accounts."
  value       = module.observability_role.arn
}
