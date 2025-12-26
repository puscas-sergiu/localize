"""DeepL API client for translation."""

import deepl
from typing import Optional, List
from dataclasses import dataclass

from ...config import config


@dataclass
class DeepLResult:
    """Result from a DeepL translation."""

    text: str
    detected_source_lang: str
    billed_characters: int


class DeepLClient:
    """Client for DeepL translation API."""

    LANGUAGE_MAP = {
        "de": "DE",
        "fr": "FR",
        "it": "IT",
        "es": "ES",
        "ro": "RO",
        "en": "EN-US",
    }

    # Languages that support formality
    FORMALITY_SUPPORTED = {"DE", "FR", "IT", "ES", "NL", "PL", "PT-BR", "PT-PT", "RU"}

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the DeepL client.

        Args:
            api_key: DeepL API key. If not provided, uses DEEPL_API_KEY from environment.
        """
        self.api_key = api_key or config.deepl_api_key
        if not self.api_key:
            raise ValueError("DeepL API key is required")
        self.translator = deepl.Translator(self.api_key)

    def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: Optional[str] = None,
        formality: str = "default",
        preserve_formatting: bool = True,
    ) -> DeepLResult:
        """
        Translate a single text.

        Args:
            text: Text to translate
            target_lang: Target language code (e.g., "de", "fr")
            source_lang: Source language code (auto-detect if not provided)
            formality: Formality level ("less", "more", "default")
            preserve_formatting: Whether to preserve text formatting

        Returns:
            DeepLResult with translation and metadata
        """
        target = self.LANGUAGE_MAP.get(target_lang.lower(), target_lang.upper())

        kwargs = {
            "text": text,
            "target_lang": target,
            "preserve_formatting": preserve_formatting,
        }

        if source_lang:
            kwargs["source_lang"] = self.LANGUAGE_MAP.get(
                source_lang.lower(), source_lang.upper()
            )

        # Only set formality for supported languages
        if formality != "default" and target in self.FORMALITY_SUPPORTED:
            kwargs["formality"] = formality

        result = self.translator.translate_text(**kwargs)

        return DeepLResult(
            text=result.text,
            detected_source_lang=result.detected_source_lang,
            billed_characters=len(text),
        )

    def translate_batch(
        self,
        texts: List[str],
        target_lang: str,
        source_lang: Optional[str] = None,
        formality: str = "default",
    ) -> List[DeepLResult]:
        """
        Translate multiple texts in a batch.

        Args:
            texts: List of texts to translate
            target_lang: Target language code
            source_lang: Source language code (auto-detect if not provided)
            formality: Formality level

        Returns:
            List of DeepLResult objects
        """
        if not texts:
            return []

        target = self.LANGUAGE_MAP.get(target_lang.lower(), target_lang.upper())

        kwargs = {
            "text": texts,
            "target_lang": target,
            "preserve_formatting": True,
        }

        if source_lang:
            kwargs["source_lang"] = self.LANGUAGE_MAP.get(
                source_lang.lower(), source_lang.upper()
            )

        if formality != "default" and target in self.FORMALITY_SUPPORTED:
            kwargs["formality"] = formality

        results = self.translator.translate_text(**kwargs)

        # Handle single result case
        if not isinstance(results, list):
            results = [results]

        return [
            DeepLResult(
                text=r.text,
                detected_source_lang=r.detected_source_lang,
                billed_characters=len(t),
            )
            for r, t in zip(results, texts)
        ]

    def get_usage(self) -> dict:
        """Get current API usage statistics."""
        usage = self.translator.get_usage()
        return {
            "character_count": usage.character.count if usage.character else 0,
            "character_limit": usage.character.limit if usage.character else 0,
        }
