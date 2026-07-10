# Security Group = pare-feu de l'instance EC2.
# Il autorise uniquement les ports necessaires au deploiement FastAPI.
resource "aws_security_group" "fastapi_sg" {
  name        = "${var.project_name}-sg"
  description = "Allow SSH, HTTP and FastAPI traffic"

  # Port 22: connexion SSH pour administrer le serveur avec Ansible.
  ingress {
    description = "SSH access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Port 80: HTTP standard, utile si on ajoute plus tard Nginx ou un proxy.
  ingress {
    description = "HTTP access"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Port 8100: port public de l'API FastAPI dans ce projet.
  ingress {
    description = "FastAPI access"
    from_port   = 8100
    to_port     = 8100
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Sortie autorisee vers Internet pour installer Docker, cloner GitHub, etc.
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-sg"
    Project     = var.project_name
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
