# Terraform - Infrastructure AWS EC2 Free Tier

Ce dossier cree une instance EC2 Ubuntu 22.04 en `t2.micro`, une Elastic IP et un Security Group pour exposer FastAPI sur le port `8100`.

MLflow et Dagster ne sont pas deployes sur EC2, car une instance Free Tier `t2.micro` dispose seulement de 1 vCPU et 1 GB RAM.

## Prerequis

- Compte AWS avec Free Tier actif
- AWS CLI configure avec `aws configure`
- Terraform installe
- Une key pair EC2 existante, par exemple `id_rsa`

## Commandes

```bash
cd terraform
terraform init
terraform plan -var="key_name=id_rsa"
terraform apply -var="key_name=id_rsa"
```

## Recuperer les informations

```bash
terraform output ec2_public_ip
terraform output ssh_command
```

## Detruire l'infrastructure

```bash
terraform destroy -var="key_name=id_rsa"
```

## Cout estime

Avec AWS Free Tier, une instance `t2.micro` Linux est generalement eligible a 0 EUR/mois dans la limite des quotas gratuits. Pense a arreter ou detruire l'instance quand elle n'est plus utilisee.
