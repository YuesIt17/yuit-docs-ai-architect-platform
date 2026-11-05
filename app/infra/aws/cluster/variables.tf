variable "project" {
  description = "Short project name used in resource names. Must match foundation."
  type        = string
  default     = "kp"
}

variable "environment" {
  description = "Environment name used in resource names and tags."
  type        = string
  default     = "lab"
}

variable "region" {
  description = "AWS region. Must match foundation."
  type        = string
  default     = "eu-north-1"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version. Upgrade before standard support ends, because extended support costs six times more."
  type        = string
  default     = "1.36"
}

variable "vpc_cidr" {
  description = "VPC address range."
  type        = string
  default     = "10.40.0.0/16"
}

variable "api_public_access_cidrs" {
  description = "Addresses allowed to reach the Kubernetes API, such as your own IP as x.x.x.x/32."
  type        = list(string)

  validation {
    condition     = length(var.api_public_access_cidrs) > 0 && !contains(var.api_public_access_cidrs, "0.0.0.0/0")
    error_message = "List at least one address range, and do not open the Kubernetes API to 0.0.0.0/0."
  }
}

variable "general_instance_type" {
  description = "Instance type for the platform, Keycloak and monitoring."
  type        = string
  default     = "t3.large"
}

variable "general_node_count" {
  description = "Number of general nodes."
  type        = number
  default     = 2
}

variable "ollama_instance_type" {
  description = "Instance type for Ollama. Avoid burstable types, because inference uses up their CPU credits."
  type        = string
  default     = "m6i.xlarge"
}

variable "ollama_node_count" {
  description = "Number of Ollama nodes. Set to 0 to save money while using the MOCK LLM."
  type        = number
  default     = 1
}

variable "node_disk_size_gb" {
  description = "Root disk size for each node, which holds container images."
  type        = number
  default     = 50
}

variable "log_retention_days" {
  description = "Days to keep EKS control plane logs in CloudWatch."
  type        = number
  default     = 7
}
