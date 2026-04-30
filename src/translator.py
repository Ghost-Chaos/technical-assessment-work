import json
import os
import re

from dotenv import load_dotenv
import requests

from .cache import content_hash
from .protected_terms import protect_text, restore_text


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.5-flash"
PROTECTED_PLACEHOLDER_RE = re.compile(r"__PROTECTED_\d+__")


def _mock_translate(text: str, language):
    code = language["code"]
    marker = "[MOCK_AR]" if code == "ar" else "[MOCK_MS]"
    return f"{marker} {text}"


def _usage_tokens(usage: dict):
    return {
        "prompt_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
        "completion_tokens": usage.get("completion_tokens") or usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def _log_translation(logger, *, segment_id, language, provider, model, status, cache_hit, source_hash, input_chars, output_chars=0, usage=None, error=None):
    usage = usage or {}
    logger.llm_call(
        {
            "segment_id": segment_id,
            "language": language["code"],
            "provider": provider,
            "model": model,
            "status": status,
            "cache_hit": cache_hit,
            "source_hash": source_hash,
            "input_chars": input_chars,
            "output_chars": output_chars,
            "usage": usage,
            "token_estimate": _usage_tokens(usage),
            "estimated_cost": None,
            "error": error,
        }
    )


def _openrouter_translate(text: str, language, api_key: str, model: str):
    prompt = (
        f"Translate the following website segment naturally into {language['name']} ({language['code']}).\n"
        "Preserve HTML tags exactly.\n"
        "Preserve placeholders, variables, and tokens exactly.\n"
        "Preserve URLs exactly.\n"
        "Preserve protected-term placeholders like __PROTECTED_0__ exactly.\n"
        "Return only the translated text.\n\n"
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
    return data["choices"][0]["message"]["content"].strip(), data.get("usage", {})


def _restore_with_safety(text: str, mapping: dict):
    restored = restore_text(text, mapping)
    unresolved = PROTECTED_PLACEHOLDER_RE.findall(restored)
    unknown = [placeholder for placeholder in unresolved if placeholder not in mapping]
    return restored, unresolved, unknown


def _combined_mapping(current_mapping: dict, cache_entry: dict | None = None):
    combined = {}
    if cache_entry:
        combined.update(cache_entry.get("placeholder_mapping") or {})
    combined.update(current_mapping)
    return combined


def translate_segments(segments, languages, protected_terms, cache, logger):
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    if api_key:
        print(f"Using OpenRouter model: {model}")
    else:
        print("OpenRouter unavailable, using mock fallback")

    translations = {language["code"]: {} for language in languages}
    stats = {"mock_calls": 0, "api_calls": 0, "cache_hits": 0}
    for language in languages:
        for segment in segments:
            protected_text, mapping = protect_text(segment["text"], protected_terms)
            key = content_hash(protected_text, language["code"])
            cache_entry = cache.get(key)
            restore_mapping = _combined_mapping(mapping, cache_entry)
            can_use_cache = bool(cache_entry and (not api_key or cache_entry.get("provider") == "openrouter"))
            if can_use_cache:
                cached_restored, cached_unresolved, _ = _restore_with_safety(cache_entry["translated_protected"], restore_mapping)
                if cached_unresolved:
                    can_use_cache = False
            if can_use_cache:
                translated_protected = cache[key]["translated_protected"]
                stats["cache_hits"] += 1
                _log_translation(
                    logger,
                    segment_id=segment["id"],
                    language=language,
                    provider=cache_entry.get("provider", "cache"),
                    model=cache_entry.get("model", model),
                    status="cache_hit",
                    cache_hit=True,
                    source_hash=key,
                    input_chars=len(protected_text),
                    output_chars=len(translated_protected),
                    usage=cache_entry.get("usage", {}),
                )
            else:
                provider = "mock"
                usage = {}
                try:
                    if api_key:
                        translated_protected, usage = _openrouter_translate(protected_text, language, api_key, model)
                        provider = "openrouter"
                    else:
                        translated_protected = None
                except Exception as exc:
                    _log_translation(
                        logger,
                        segment_id=segment["id"],
                        language=language,
                        provider="openrouter",
                        model=model,
                        status="error",
                        cache_hit=False,
                        source_hash=key,
                        input_chars=len(protected_text),
                        output_chars=0,
                        error=str(exc),
                    )
                    translated_protected = None
                if translated_protected is None:
                    translated_protected = _mock_translate(protected_text, language)
                    _log_translation(
                        logger,
                        segment_id=segment["id"],
                        language=language,
                        provider="mock",
                        model="mock",
                        status="success",
                        cache_hit=False,
                        source_hash=key,
                        input_chars=len(protected_text),
                        output_chars=len(translated_protected),
                    )
                    stats["mock_calls"] += 1
                else:
                    _log_translation(
                        logger,
                        segment_id=segment["id"],
                        language=language,
                        provider=provider,
                        model=model,
                        status="success",
                        cache_hit=False,
                        source_hash=key,
                        input_chars=len(protected_text),
                        output_chars=len(translated_protected),
                        usage=usage,
                    )
                    stats["api_calls"] += 1
                restored_text, unresolved, unknown = _restore_with_safety(translated_protected, restore_mapping)
                if unresolved:
                    # Treat unmapped protected placeholders as an unsafe translation and
                    # fall back to the deterministic local translator for this segment.
                    translated_protected = _mock_translate(protected_text, language)
                    restored_text, _, _ = _restore_with_safety(translated_protected, mapping)
                    provider = "mock"
                    usage = {}
                cache[key] = {
                    "language": language["code"],
                    "provider": provider,
                    "model": model if provider == "openrouter" else "mock",
                    "source_protected": protected_text,
                    "translated_protected": translated_protected,
                    "placeholder_mapping": mapping,
                    "usage": usage,
                }
            cache_entry = cache.get(key)
            restore_mapping = _combined_mapping(mapping, cache_entry)
            restored_text, unresolved, unknown = _restore_with_safety(translated_protected, restore_mapping)
            translations[language["code"]][segment["id"]] = {
                "source": segment["text"],
                "protected_source": protected_text,
                "translated": restored_text,
                "placeholder_mapping": restore_mapping,
                "unresolved_protected_placeholders": unresolved,
                "missing_placeholder_mappings": unknown,
            }
    return translations, stats
