# Deploiement AWS EC2 (Free Tier)

Ce guide deploie uniquement FastAPI sur une EC2 `t2.micro` Ubuntu 22.04. MLflow et Dagster restent en local, car lancer tous les services Docker Compose sur 1 GB RAM serait trop lourd.

## Prerequis

- Compte AWS avec Free Tier actif
- AWS CLI configure: `aws configure`
- Terraform installe
- Ansible installe
- Une key pair EC2 existante, par exemple `id_rsa`
- Docker en local si tu veux tester l'image avant de deployer

## Etape 1 : Creer l'infrastructure (Terraform)

```bash
cd terraform
terraform init
terraform plan -var="key_name=id_rsa"
terraform apply -var="key_name=id_rsa"
terraform output -raw ec2_public_ip
```

Terraform cree:

- une instance EC2 Ubuntu 22.04 `t2.micro`
- une Elastic IP
- un Security Group avec les ports `22`, `80` et `8100`
- Docker et Docker Compose installes au boot via `user_data`

## Etape 2 : Configurer le serveur (Ansible)

Copie l'IP donnee par Terraform dans `ansible/inventory.ini`.

```ini
[fastapi_server]
<EC2_IP> ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa
```

Puis lance:

```bash
cd ansible
ansible-playbook -i inventory.ini playbook.yml
```

Ansible installe les paquets utiles, verifie Docker, clone le repo, cree un Compose leger pour FastAPI uniquement, puis demarre le service.

## Etape 3 : Uploader les donnees Olist

Si les donnees sont necessaires sur l'instance:

```bash
scp -r ./data ubuntu@<EC2_IP>:/data/olist/
```

Pour ce deploiement Free Tier, l'API expose surtout `/health` et `/docs`. Le modele MLflow n'est pas servi depuis EC2, donc `/predict` peut retourner `503` tant qu'aucun modele n'est disponible.

## Etape 4 : Verifier le deploiement

```bash
curl http://<EC2_IP>:8100/health
```

Sur le serveur:

```bash
ssh -i ~/.ssh/id_rsa ubuntu@<EC2_IP>
check_services.sh
docker ps
```

## Etape 5 : Acceder a l'API

- FastAPI: `http://<EC2_IP>:8100`
- Documentation Swagger: `http://<EC2_IP>:8100/docs`
- Health check: `http://<EC2_IP>:8100/health`

## Arreter l'instance (pour economiser le free tier)

```bash
aws ec2 stop-instances --instance-ids <INSTANCE_ID> --region eu-west-3
```

Pour redemarrer:

```bash
aws ec2 start-instances --instance-ids <INSTANCE_ID> --region eu-west-3
```

L'Elastic IP garde la meme IP publique.

## Detruire l'infrastructure

Quand le projet est termine:

```bash
cd terraform
terraform destroy -var="key_name=id_rsa"
```

Cette commande supprime l'instance, l'Elastic IP et le Security Group crees par Terraform.
