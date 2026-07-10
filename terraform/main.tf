# Terraform minimal pour deployer FastAPI sur une EC2 Free Tier.
# MLflow et Dagster restent en local car t2.micro a seulement 1 GB de RAM.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Provider AWS: toutes les ressources seront creees dans var.region.
provider "aws" {
  region = var.region
}

# AMI Ubuntu 22.04 LTS officielle Canonical.
# Cette recherche evite de figer une AMI trop ancienne tout en restant sur Jammy 22.04.
data "aws_ami" "ubuntu_2204" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Script execute automatiquement au premier demarrage de l'instance.
# Il installe Docker et le plugin Docker Compose pour que Ansible puisse lancer FastAPI.
locals {
  user_data = <<-EOF
    #!/bin/bash
    set -eux

    apt-get update -y
    apt-get install -y ca-certificates curl gnupg lsb-release

    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list

    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    systemctl enable docker
    systemctl start docker
    usermod -aG docker ubuntu
  EOF
}

# Instance EC2 Ubuntu 22.04.
# key_name doit correspondre a une cle existante dans AWS EC2 Key Pairs.
resource "aws_instance" "fastapi" {
  ami                    = data.aws_ami.ubuntu_2204.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.fastapi_sg.id]
  user_data              = local.user_data

  tags = {
    Name        = "${var.project_name}-fastapi"
    Project     = var.project_name
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

# Elastic IP: garde une IP publique stable meme si l'instance redemarre.
resource "aws_eip" "fastapi_ip" {
  domain = "vpc"

  tags = {
    Name        = "${var.project_name}-eip"
    Project     = var.project_name
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

# Association entre l'Elastic IP et l'instance EC2.
resource "aws_eip_association" "fastapi_ip_assoc" {
  instance_id   = aws_instance.fastapi.id
  allocation_id = aws_eip.fastapi_ip.id
}
