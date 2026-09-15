"""Ordre canonique des features pour le modele SatisfactionClassifier."""

FEATURE_ORDER: list[str] = [
    "review_comment_message",
    "delivery_delay_days",
    "review_comment_length",
    "has_comment",
    "payment_type_encoded",
]
