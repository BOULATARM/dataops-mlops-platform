# IP publique stable de l'instance. A copier dans ansible/inventory.ini.
output "public_ip" {
  description = "Elastic public IP of the EC2 instance."
  value       = aws_eip.fastapi_ip.public_ip
}

# Alias pratique pour les commandes Ansible demandees dans le guide.
output "ec2_public_ip" {
  description = "Same value as public_ip, named for Ansible documentation."
  value       = aws_eip.fastapi_ip.public_ip
}

# DNS public AWS de l'instance.
output "public_dns" {
  description = "Public DNS of the EC2 instance."
  value       = aws_instance.fastapi.public_dns
}

# Commande SSH prete a l'emploi.
output "ssh_command" {
  description = "SSH command to connect to the EC2 instance."
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.fastapi_ip.public_ip}"
}
