"""
Ordre canonique des features pour le modèle SatisfactionClassifier.

Cette liste est la source unique de vérité partagée entre :
  - ml/training/config.py  (entraînement — NUMERIC_FEATURES doit correspondre)
  - api/model_loader.py    (inférence — construction du DataFrame d'entrée)

Changer l'ordre ici sans réentraîner le modèle produit des prédictions fausses.
"""

FEATURE_ORDER: list[str] = [
    "delivery_delay_days",
    "review_comment_length",
    "has_comment",
    "payment_type_encoded",
]
