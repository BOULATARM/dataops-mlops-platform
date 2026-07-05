# Vision du projet — mlops-dataops-platform

**Livrable 1 — Vision du projet**
**Auteur** : Mouad (Product Owner)

---

## 1. Problématique

Olist, plateforme e-commerce brésilienne, met en relation des vendeurs
indépendants et des clients finaux. La satisfaction client, mesurée par les
avis laissés après livraison, est un signal critique mais **découvert
tardivement** : l'avis n'est déposé qu'après réception de la commande, une
fois le mal potentiellement fait (retard de livraison, produit non conforme).

Par ailleurs, les données brutes issues des différents systèmes (commandes,
paiements, avis, vendeurs, géolocalisation) sont dispersées dans des fichiers
CSV/JSON hétérogènes, sans couche de nettoyage, de tests de qualité ni de
traçabilité — rendant toute analyse fiable difficile et toute automatisation
risquée.

**Question centrale** : peut-on anticiper, à partir de signaux disponibles
avant ou pendant la livraison (délai, moyen de paiement, présence d'un
commentaire), si un client sera satisfait ou non — et exposer cette prédiction
de façon fiable, traçable et industrialisée ?

## 2. Objectifs

1. Construire un pipeline de données bout-en-bout, fiable et testé, organisé
   en architecture médaillon (Bronze/Silver/Gold) sur les données Olist.
2. Industrialiser un modèle de classification de la satisfaction client
   (`satisfied = 1` si `review_score >= 4`), avec tracking des expériences
   et un registry de modèles versionné.
3. Exposer ce modèle via une API de prédiction fiable, observable et
   conteneurisée, intégrée dans une chaîne CI/CD automatisée.
4. Orchestrer l'ensemble du pipeline (ingestion → transformation → ML →
   serving) de façon planifiée et reproductible, sans intervention manuelle.
5. Documenter le projet (architecture, runbook, dictionnaire de données,
   contrat de données) pour qu'il reste opérable et évolutif par toute
   l'équipe, au-delà de ses auteurs initiaux.

## 3. Utilisateurs cibles

| Utilisateur | Besoin |
|---|---|
| **Data Engineers** (ingestion/transformation/qualité) | Pipeline fiable, testé, avec data contract explicite pour ne pas casser les couches avales |
| **Data Analysts** | Tables Gold propres et documentées pour produire des analyses métier (RFM, performance produit/vendeur) |
| **ML Engineers** | Feature set stable en Gold, tracking MLflow pour comparer les expériences et un registry pour déployer sans ambiguïté |
| **Équipe produit / management Olist** | Prédiction de satisfaction exploitable pour prioriser les actions correctives (relance vendeur, SAV proactif) |
| **Équipe DevOps / Scrum Master** | CI/CD fiable, documentation agile à jour, stack Docker reproductible pour tout environnement |

## 4. Valeur métier

- **Anticipation du risque d'insatisfaction** : identifier en amont les
  commandes à risque (retard de livraison important, absence de commentaire
  après un score bas) pour déclencher une action corrective avant que le
  client ne se détourne de la plateforme.
- **Fiabilisation de la donnée** : une couche Silver testée et un data
  contract explicite réduisent le risque d'erreurs silencieuses dans les
  KPIs business (CA, RFM, performance vendeur) consommés par le reporting.
- **Vélocité d'itération ML** : le tracking MLflow et le feature set Gold
  stable permettent de réentraîner et comparer des modèles sans réécrire le
  pipeline de données à chaque itération.
- **Réduction du risque opérationnel** : CI/CD (lint, tests dbt, tests API,
  build Docker, smoke test) détecte les régressions avant qu'elles n'atteignent
  la production, plutôt qu'après un incident client.

## 5. Data Strategy

- **Source de vérité unique** : DuckDB (`warehouse/duckdb/olist.duckdb`),
  un seul moteur de stockage pour les 3 couches, pas de duplication de logique
  de transformation entre outils.
- **Traçabilité de bout en bout** : chaque ligne Bronze porte son origine
  (`_source_file`, `_batch_id`, `_loaded_at`) ; chaque transformation Silver/Gold
  est versionnée et testée par dbt ; chaque run ML est tracé par MLflow.
  L'objectif est de pouvoir répondre à tout moment à la question
  « d'où vient cette valeur, et par quelle transformation est-elle passée ? ».
- **Qualité par contrat, pas par contrôle a posteriori** : le data contract
  (`docs/data_contract.md`) et les tests dbt (génériques + custom) valident
  chaque build avant que la donnée n'atteigne la couche Gold ou le feature set
  ML — la qualité est une porte de build, pas un audit après incident.
- **Séparation stricte Bronze (brut) / Silver (nettoyé) / Gold (métier)** :
  aucune transformation en Bronze, pas de logique métier en Silver, pas de
  ré-ingestion de données brutes en Gold — chaque couche a une responsabilité
  unique, ce qui simplifie le debug et l'évolution du schéma.
- **Reproductibilité** : l'ensemble du pipeline (ingestion, transformation,
  entraînement, serving) est exécutable aussi bien en local qu'en Docker qu'en
  CI, à partir des mêmes fichiers sources et des mêmes commandes documentées
  dans `docs/runbook.md`.
