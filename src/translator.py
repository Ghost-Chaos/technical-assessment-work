import json
import os

import requests

from .cache import content_hash
from .protected_terms import protect_text, restore_text


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _mock_translate(text: str, language):
    code = language["code"]
    marker = "[MOCK_AR]" if code == "ar" else "[MOCK_MS]"
    return f"{marker} {text}"


def _openrouter_translate(text: str, language, logger):
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    if not api_key:
        return None
    prompt = (
        f"Translate the following website segment into {language['name']} ({language['code']}). "
        "Keep placeholders like __PROTECTED_0__ unchanged. Return only the translation.\n\n"
        f"{text}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a careful website localization translator."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    response = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    logger.llm_call(
        {
            "provider": "openrouter",
            "model": model,
            "language": language["code"],
            "input_chars": len(text),
            "response_usage": data.get("usage", {}),
        }
    )
    return data["choices"][0]["message"]["content"].strip()


def translate_segments(segments, languages, protected_terms, cache, logger):
    translations = {language["code"]: {} for language in languages}
    stats = {"mock_calls": 0, "api_calls": 0, "cache_hits": 0}
    for language in languages:
        for segment in segments:
            protected_text, mapping = protect_text(segment["text"], protected_terms)
            key = content_hash(protected_text, language["code"])
            if key in cache:
                translated_protected = cache[key]["translated_protected"]
                stats["cache_hits"] += 1
                logger.llm_call(
                    {
                        "provider": "cache",
                        "language": language["code"],
                        "segment_id": segment["id"],
                        "input_chars": len(protected_text),
                    }
                )
            else:
                try:
                    translated_protected = _openrouter_translate(protected_text, language, logger)
                except Exception as exc:
                    logger.llm_call(
                        {
                            "provider": "openrouter",
                            "language": language["code"],
                            "segment_id": segment["id"],
                            "error": str(exc),
                        }
                    )
                    translated_protected = None
                if translated_protected is None:
                    translated_protected = _mock_translate(protected_text, language)
                    logger.llm_call(
                        {
                            "provider": "mock",
                            "language": language["code"],
                            "segment_id": segment["id"],
                            "input_chars": len(protected_text),
                            "output_chars": len(translated_protected),
                        }
                    )
                    stats["mock_calls"] += 1
                else:
                    stats["api_calls"] += 1
                cache[key] = {
                    "language": language["code"],
                    "source_protected": protected_text,
                    "translated_protected": translated_protected,
                }
            translations[language["code"]][segment["id"]] = {
                "source": segment["text"],
                "protected_source": protected_text,
                "translated": restore_text(translated_protected, mapping),
                "placeholder_mapping": mapping,
            }
    return translations, stats
