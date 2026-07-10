# Region AWS cible. eu-west-3 correspond a Paris.
variable "region" {
  description = "AWS region used to deploy the EC2 instance."
  type        = string
  default     = "eu-west-3"
}

# Type d'instance Free Tier. t2.micro = 1 vCPU, 1 GB RAM.
variable "instance_type" {
  description = "EC2 instance type. Keep t2.micro for AWS Free Tier."
  type        = string
  default     = "t3.micro"
}

# Nom d'une cle SSH deja creee dans AWS EC2 Key Pairs.
# Elle permet de se connecter avec: ssh -i ~/.ssh/id_rsa ubuntu@<ip>
variable "key_name" {
  description = "Name of the existing AWS EC2 key pair used for SSH."
  type        = string
}

# Nom logique du projet. Reutilise dans les tags et les noms AWS.
variable "project_name" {
  description = "Project name used for AWS resource names and tags."
  type        = string
  default     = "dataops-mlops-platform"
}
