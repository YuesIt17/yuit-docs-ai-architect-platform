variable "name" {
  description = "Globally unique bucket name."
  type        = string
}

variable "noncurrent_version_days" {
  description = "Days to keep previous object versions."
  type        = number
  default     = 30
}

variable "expiration_days" {
  description = "Days before current objects expire. Null keeps them until deleted."
  type        = number
  default     = null
}
