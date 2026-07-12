from functools import lru_cache
from typing import Any

FR_EN_MODEL_NAME = "Helsinki-NLP/opus-mt-fr-en"
EN_PT_MODEL_NAME = "Helsinki-NLP/opus-mt-en-ROMANCE"


@lru_cache(maxsize=1)
def _load_translation_models() -> tuple[Any, Any, Any, Any, Any]:
    """
    Charge les dépendances et les modèles seulement lors de la première
    traduction.

    Cela évite d'exiger torch et transformers au simple import de FastAPI,
    notamment pendant les tests unitaires GitHub Actions.
    """
    try:
        import torch
        from transformers import MarianMTModel, MarianTokenizer
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Les dépendances de traduction sont absentes. "
            "Installez torch, transformers, sentencepiece et sacremoses."
        ) from exc

    fr_en_tokenizer = MarianTokenizer.from_pretrained(FR_EN_MODEL_NAME)
    fr_en_model = MarianMTModel.from_pretrained(FR_EN_MODEL_NAME)
    fr_en_model.eval()

    en_pt_tokenizer = MarianTokenizer.from_pretrained(EN_PT_MODEL_NAME)
    en_pt_model = MarianMTModel.from_pretrained(EN_PT_MODEL_NAME)
    en_pt_model.eval()

    return (
        torch,
        fr_en_tokenizer,
        fr_en_model,
        en_pt_tokenizer,
        en_pt_model,
    )


def _translate(
    text: str,
    tokenizer: Any,
    model: Any,
    torch_module: Any,
    language_prefix: str = "",
) -> str:
    prepared_text = f"{language_prefix}{text}"

    encoded = tokenizer(
        prepared_text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )

    with torch_module.inference_mode():
        generated = model.generate(
            **encoded,
            max_new_tokens=256,
        )

    return tokenizer.decode(
        generated[0],
        skip_special_tokens=True,
    ).strip()


def translate_french_to_portuguese(text: str) -> str:
    """
    Traduit un commentaire :
    français -> anglais -> portugais brésilien.
    """
    cleaned_text = text.strip()

    if not cleaned_text:
        return ""

    (
        torch_module,
        fr_en_tokenizer,
        fr_en_model,
        en_pt_tokenizer,
        en_pt_model,
    ) = _load_translation_models()

    english_text = _translate(
        cleaned_text,
        fr_en_tokenizer,
        fr_en_model,
        torch_module,
    )

    portuguese_text = _translate(
        english_text,
        en_pt_tokenizer,
        en_pt_model,
        torch_module,
        language_prefix=">>pt_BR<< ",
    )

    return portuguese_text
