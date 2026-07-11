from functools import lru_cache

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


FR_EN_MODEL = "Helsinki-NLP/opus-mt-fr-en"
EN_PT_MODEL = "Helsinki-NLP/opus-mt-en-ROMANCE"


@lru_cache(maxsize=1)
def load_translation_models():
    """
    Charge les deux modèles une seule fois :
    français → anglais → portugais brésilien.
    """
    fr_en_tokenizer = AutoTokenizer.from_pretrained(FR_EN_MODEL)
    fr_en_model = AutoModelForSeq2SeqLM.from_pretrained(FR_EN_MODEL)
    fr_en_model.eval()

    en_pt_tokenizer = AutoTokenizer.from_pretrained(EN_PT_MODEL)
    en_pt_model = AutoModelForSeq2SeqLM.from_pretrained(EN_PT_MODEL)
    en_pt_model.eval()

    return (
        fr_en_tokenizer,
        fr_en_model,
        en_pt_tokenizer,
        en_pt_model,
    )


def translate_text(
    text: str,
    tokenizer,
    model,
    prefix: str = "",
) -> str:
    source_text = f"{prefix}{text}" if prefix else text

    inputs = tokenizer(
        [source_text],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=256,
    )

    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=256,
        )

    return tokenizer.batch_decode(
        generated,
        skip_special_tokens=True,
    )[0]


def translate_french_to_portuguese(text: str) -> str:
    """
    Traduit un commentaire français vers le portugais brésilien.
    """
    text = (text or "").strip()

    if not text:
        return ""

    (
        fr_en_tokenizer,
        fr_en_model,
        en_pt_tokenizer,
        en_pt_model,
    ) = load_translation_models()

    english_text = translate_text(
        text,
        fr_en_tokenizer,
        fr_en_model,
    )

    portuguese_text = translate_text(
        english_text,
        en_pt_tokenizer,
        en_pt_model,
        prefix=">>pt_BR<< ",
    )

    return portuguese_text.strip()
