"""Configuration management for the localization pipeline."""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration."""

    # API Keys
    deepl_api_key: str = field(default_factory=lambda: os.getenv("DEEPL_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # Translation settings
    quality_threshold: float = field(
        default_factory=lambda: float(os.getenv("QUALITY_THRESHOLD", "80"))
    )
    target_languages: List[str] = field(
        default_factory=lambda: os.getenv("TARGET_LANGUAGES", "de,fr,it,es,ro").split(",")
    )

    # OpenAI model settings
    openai_model: str = "gpt-5-mini-2025-08-07"
    openai_temperature: float = 0.3

    # Batch translation settings
    deepl_batch_size: int = 50
    openai_batch_size: int = 20
    openai_batch_max_tokens: int = 4000

    # DeepL language mapping
    DEEPL_LANGUAGE_MAP: dict = field(default_factory=lambda: {
        "de": "DE",
        "fr": "FR",
        "it": "IT",
        "es": "ES",
        "ro": "RO",
        "en": "EN-US",
    })

    # Language display names (for prompts)
    LANGUAGE_NAMES: dict = field(default_factory=lambda: {
        "de": "German",
        "fr": "French",
        "it": "Italian",
        "es": "Spanish",
        "ro": "Romanian",
        "en": "English",
    })

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        if not self.deepl_api_key:
            errors.append("DEEPL_API_KEY is not set")
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is not set")
        return errors


# Global config instance
config = Config()
