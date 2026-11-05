variable "project" {
  description = "Short project name used in resource names."
  type        = string
  default     = "kp"
}

variable "environment" {
  description = "Environment name used in tags."
  type        = string
  default     = "lab"
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "eu-north-1"
}

variable "ecr_repositories" {
  description = "Container image repositories to create."
  type        = set(string)
  default     = ["kp-api", "kp-frontend"]
}

variable "ecr_images_to_keep" {
  description = "Newest images to keep in each repository."
  type        = number
  default     = 10
}

variable "observability_retention_days" {
  description = "Days to keep Loki and Tempo objects."
  type        = number
  default     = 30
}
