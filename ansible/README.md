# Ansible - Configuration EC2 et deploiement FastAPI

Ce dossier configure l'instance EC2 creee par Terraform et deploie uniquement FastAPI. MLflow et Dagster restent en local pour respecter la limite AWS Free Tier `t2.micro`.

## 1. Recuperer l'IP depuis Terraform

```bash
cd terraform
terraform output -raw ec2_public_ip
```

## 2. Mettre a jour l'inventory

Dans `ansible/inventory.ini`, remplacer `0.0.0.0` par l'IP publique EC2.

Verifier aussi le chemin de cle SSH:

```ini
ansible_ssh_private_key_file=~/.ssh/id_rsa
```

## 3. Uploader les donnees Olist

Depuis la racine du projet local:

```bash
scp -r ./data ubuntu@<IP>:/data/olist/
```

## 4. Lancer le playbook

```bash
cd ansible
ansible-playbook -i inventory.ini playbook.yml
```

## 5. Tester l'API

```bash
curl http://<IP>:8100/health
```

URLs apres deploiement:

- FastAPI: `http://<EC2_IP>:8100`
- FastAPI docs: `http://<EC2_IP>:8100/docs`

## Monitoring simple

Sur le serveur:

```bash
ssh -i ~/.ssh/id_rsa ubuntu@<IP>
check_services.sh
htop
ncdu /
```
