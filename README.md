# Technical Assessment Work

## Starter Template

This repository is ready for a timed technical assessment. It includes a minimal Python project structure, sample data and output folders, and a place for tests.

## Multilingual Translation Pipeline MVP

Run the pipeline:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Optional: add OPENROUTER_API_KEY to .env for real translations.
python main.py
```

Validate the generated artifacts:

```bash
python validate.py
```

The pipeline reads `pages.json` and `target_languages.json`, fetches Deriv pages with a sample fallback, extracts translatable HTML segments, protects product terms and tokens, translates through OpenRouter when `OPENROUTER_API_KEY` is set, and otherwise uses a clearly marked mock translator.
