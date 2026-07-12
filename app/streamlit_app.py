import os

import pandas as pd
import requests
import streamlit as st


# Adresse de l'API FastAPI
FASTAPI_URL = os.environ.get("FASTAPI_URL", "http://localhost:8100")


# Configuration de la page
st.set_page_config(
    page_title="Prédicteur Satisfaction Olist",
    page_icon="🛍️",
    layout="wide",
)

st.title("🛍️ Prédicteur de Satisfaction Client Olist")
st.markdown("**Plateforme MLOps & DataOps — Module DSBD**")


# ============================================================
# Barre latérale : état de FastAPI et du modèle
# ============================================================
with st.sidebar:
    st.header("📊 Statut du système")

    try:
        health_response = requests.get(
            f"{FASTAPI_URL}/health",
            timeout=5,
        )
        health_response.raise_for_status()
        health = health_response.json()

        if health.get("model_loaded"):
            model_name = health.get("model_name", "Inconnu")
            model_version = health.get("model_version", "Inconnue")

            st.success(
                f"✅ Modèle : {model_name}\n\n"
                f"Version : {model_version}"
            )
        else:
            st.error("❌ Modèle non chargé")

            if health.get("load_error"):
                st.caption(health["load_error"])

    except requests.RequestException as error:
        st.error("❌ API non accessible")
        st.caption(str(error))

    except ValueError:
        st.error("❌ Réponse API invalide")

    st.info(f"🔗 API : {FASTAPI_URL}")


# ============================================================
# Initialisation de l'historique
# ============================================================
if "historique" not in st.session_state:
    st.session_state.historique = []


# ============================================================
# Formulaire
# ============================================================
st.subheader("📝 Formulaire de prédiction")

col1, col2 = st.columns(2)

with col1:
    commentaire = st.text_area(
        "Commentaire client",
        placeholder="Exemple : Produit excellent !",
        height=150,
    )

    delivery_delay = st.number_input(
        "Jours de retard livraison",
        min_value=-30,
        max_value=100,
        value=0,
        step=1,
    )

with col2:
    comment_length = len(commentaire.strip()) if commentaire else 0

    st.metric(
        "Longueur du commentaire",
        comment_length,
    )

    has_comment = 1 if commentaire.strip() else 0

    st.info(
        f"Commentaire : {'✅ Oui' if has_comment else '❌ Non'}"
    )

    payment_options = {
        "Carte de crédit": 1,
        "Boleto": 2,
        "Voucher": 3,
        "Carte de débit": 4,
    }

    payment_label = st.selectbox(
        "Type de paiement",
        list(payment_options.keys()),
    )

    payment_encoded = payment_options[payment_label]


# ============================================================
# Prédiction
# ============================================================
if st.button(
    "🔮 Prédire",
    type="primary",
    use_container_width=True,
):
    payload = {
        "review_comment_message": commentaire.strip(),
        "delivery_delay_days": int(delivery_delay),
        "review_comment_length": int(comment_length),
        "has_comment": int(has_comment),
        "payment_type_encoded": int(payment_encoded),
    }

    try:
        with st.spinner("Prédiction en cours..."):
            response = requests.post(
                f"{FASTAPI_URL}/predict",
                json=payload,
                timeout=15,
            )

        result = response.json()

        if not response.ok:
            st.error(f"Erreur API HTTP {response.status_code}")
            st.json(result)

        elif "satisfied" in result:
            # Réponse réelle de ton API
            satisfied = bool(result["satisfied"])
            satisfaction_probability = float(
                result.get("probability", 0.0)
            )

            # Sécuriser la valeur entre 0 et 1
            satisfaction_probability = max(
                0.0,
                min(1.0, satisfaction_probability),
            )

            if satisfied:
                predicted_label = "😊 Satisfait"
                confidence = satisfaction_probability
            else:
                predicted_label = "😞 Insatisfait"
                confidence = 1 - satisfaction_probability

            st.divider()
            st.subheader("🎯 Résultat de la prédiction")

            if satisfied:
                st.success("## 🟢 Client probablement SATISFAIT")
            else:
                st.warning("## 🔴 Client probablement INSATISFAIT")

            metric_col1, metric_col2, metric_col3 = st.columns(3)

            with metric_col1:
                st.metric(
                    "Probabilité de satisfaction",
                    f"{satisfaction_probability:.1%}",
                )

            with metric_col2:
                st.metric(
                    "Probabilité d'insatisfaction",
                    f"{1 - satisfaction_probability:.1%}",
                )

            with metric_col3:
                st.metric(
                    "Confiance de la décision",
                    f"{confidence:.1%}",
                )

            model_name = result.get(
                "model_name",
                "Inconnu",
            )

            model_version = result.get(
                "model_version",
                "Inconnue",
            )

            st.caption(
                f"Modèle utilisé : {model_name} — "
                f"Version : {model_version}"
            )

            # Ajouter la prédiction dans l'historique
            st.session_state.historique.insert(
                0,
                {
                    "Commentaire": (
                        commentaire[:50]
                        if commentaire
                        else "Aucun commentaire"
                    ),
                    "Résultat": predicted_label,
                    "Confiance": f"{confidence:.1%}",
                    "Satisfaction": f"{satisfaction_probability:.1%}",
                    "Retard": int(delivery_delay),
                    "Paiement": payment_label,
                },
            )

        else:
            st.error("Format de réponse API inattendu")
            st.json(result)

    except requests.Timeout:
        st.error(
            "L'API a mis trop de temps à répondre."
        )

    except requests.ConnectionError:
        st.error(
            f"Impossible de joindre FastAPI à l'adresse "
            f"{FASTAPI_URL}."
        )

    except requests.RequestException as error:
        st.error(f"Erreur de connexion : {error}")

    except ValueError:
        st.error(
            "FastAPI n'a pas renvoyé une réponse JSON valide."
        )

    except Exception as error:
        st.error(f"Erreur inattendue : {error}")


# ============================================================
# Historique des prédictions
# ============================================================
if st.session_state.historique:
    st.divider()
    st.subheader("📋 Historique des prédictions")

    if st.button("🗑️ Effacer l'historique"):
        st.session_state.historique = []
        st.rerun()

    historique_df = pd.DataFrame(
        st.session_state.historique[:10]
    )

    st.dataframe(
        historique_df,
        use_container_width=True,
        hide_index=True,
    )
