"""OpenAI GPT-4 client for translation fallback."""

import json
from typing import Optional, Dict, List
from openai import OpenAI

from ...config import config


class OpenAIClient:
    """Client for OpenAI GPT-4 translation (fallback provider)."""

    LANGUAGE_NAMES = {
        "de": "German",
        "fr": "French",
        "it": "Italian",
        "es": "Spanish",
        "ro": "Romanian",
        "en": "English",
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY from environment.
        """
        self.api_key = api_key or config.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        self.client = OpenAI(api_key=self.api_key)
        self.model = config.openai_model
        self.temperature = config.openai_temperature

    def translate(
        self,
        text: str,
        target_lang: str,
        context: Optional[str] = None,
        glossary: Optional[Dict[str, str]] = None,
        app_context: str = "language learning app",
    ) -> str:
        """
        Translate text using GPT-4.

        Args:
            text: Text to translate
            target_lang: Target language code (e.g., "de", "fr")
            context: Optional context about where/how the string is used
            glossary: Optional dictionary of terms to use consistently
            app_context: Description of the app context

        Returns:
            Translated text
        """
        lang_name = self.LANGUAGE_NAMES.get(target_lang.lower(), target_lang)

        system_prompt = self._build_system_prompt(lang_name, glossary, app_context)
        user_prompt = self._build_user_prompt(text, lang_name, context)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_completion_tokens=500,
        )

        result = response.choices[0].message.content.strip()

        # Clean up common GPT formatting issues
        result = self._clean_response(result)

        return result

    def translate_batch(
        self,
        texts: List[str],
        target_lang: str,
        context: Optional[str] = None,
        glossary: Optional[Dict[str, str]] = None,
        app_context: str = "language learning app",
    ) -> List[str]:
        """
        Translate multiple texts in a single API call using JSON format.

        Args:
            texts: List of texts to translate
            target_lang: Target language code
            context: Optional shared context for all strings
            glossary: Optional glossary
            app_context: App description

        Returns:
            List of translated texts in same order as input
        """
        if not texts:
            return []

        lang_name = self.LANGUAGE_NAMES.get(target_lang.lower(), target_lang)

        # Build batch request
        batch_items = [{"id": str(i), "text": t} for i, t in enumerate(texts)]

        system_prompt = self._build_batch_system_prompt(lang_name, glossary, app_context)
        user_prompt = self._build_batch_user_prompt(batch_items, lang_name, context)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_completion_tokens=config.openai_batch_max_tokens,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content.strip()
        parsed = self._parse_batch_response(result_text)

        # Ensure order matches input by using IDs
        result_map = {item["id"]: item.get("translation", "") for item in parsed}
        return [result_map.get(str(i), "") for i in range(len(texts))]

    def _build_batch_system_prompt(
        self,
        lang_name: str,
        glossary: Optional[Dict[str, str]],
        app_context: str,
    ) -> str:
        """Build system prompt for batch JSON translation."""
        prompt = f"""You are an expert iOS app translator for a {app_context} called MintDeck.

You will receive a JSON object with a "translations" array. Each item has "id" and "text".
Return a JSON object with a "translations" array. Each item must have "id" and "translation".
The order and IDs must match exactly.

CRITICAL RULES:
1. Return ONLY valid JSON - no explanations, no markdown
2. Preserve ALL iOS format specifiers exactly: %@, %d, %ld, %lld, %f, %.2f, %%, %1$@, %2$lld
3. Positional specifiers (%1$@, %2$@) may be reordered but MUST use the same numbers
4. Keep translations concise for mobile UI
5. Preserve emojis and whitespace exactly
6. If unable to translate an item, use the original text"""

        if glossary:
            prompt += "\n\nGLOSSARY:\n"
            for term, translation in glossary.items():
                prompt += f"- '{term}' -> '{translation}'\n"

        return prompt

    def _build_batch_user_prompt(
        self,
        batch_items: List[Dict[str, str]],
        lang_name: str,
        context: Optional[str],
    ) -> str:
        """Build user prompt for batch translation."""
        request_obj = {"translations": batch_items}
        prompt = f"Translate to {lang_name}:\n\n{json.dumps(request_obj, indent=2)}"

        if context:
            prompt += f"\n\n[UI Context: {context}]"

        return prompt

    def _parse_batch_response(self, response: str) -> List[Dict[str, str]]:
        """Parse JSON response from batch translation."""
        try:
            data = json.loads(response)
            # Handle both direct array and wrapped object
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "translations" in data:
                return data["translations"]
            else:
                raise ValueError("Unexpected JSON structure")
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse batch response: {e}")

    def _build_system_prompt(
        self,
        lang_name: str,
        glossary: Optional[Dict[str, str]],
        app_context: str,
    ) -> str:
        """Build the system prompt for translation."""
        prompt = f"""You are an expert iOS app translator for a {app_context} called MintDeck.

CRITICAL RULES - FOLLOW EXACTLY:
1. Preserve ALL iOS format specifiers EXACTLY as they appear:
   - %@ (object/string placeholder)
   - %d, %ld, %lld (integer placeholders)
   - %f, %.2f (float placeholders)
   - %% (literal percent sign)
   - Positional specifiers like %1$@, %2$lld MUST stay in the translation

2. The ORDER of positional placeholders may change in translation (e.g., %1$@ might come after %2$@ in the translated sentence), but you MUST use the SAME numbered placeholders.

3. Keep translations concise - mobile UI has limited space.

4. Use natural, conversational tone appropriate for language learners.

5. Preserve emojis exactly as they appear.

6. Preserve any leading/trailing whitespace or newlines.

7. Respond with ONLY the translated text, nothing else.
   - No quotes around the translation
   - No explanations or notes
   - No "Translation:" prefix

8. If translation is absolutely impossible, respond with: [UNABLE]"""

        if glossary:
            prompt += "\n\nGLOSSARY (use these exact terms in your translation):\n"
            for term, translation in glossary.items():
                prompt += f"- '{term}' → '{translation}'\n"

        return prompt

    def _build_user_prompt(
        self,
        text: str,
        lang_name: str,
        context: Optional[str],
    ) -> str:
        """Build the user prompt for translation."""
        prompt = f"Translate to {lang_name}:\n{text}"

        if context:
            prompt += f"\n\n[UI Context: {context}]"

        return prompt

    def _clean_response(self, response: str) -> str:
        """Clean up common GPT formatting issues."""
        # Remove surrounding quotes if present
        if (response.startswith('"') and response.endswith('"')) or (
            response.startswith("'") and response.endswith("'")
        ):
            response = response[1:-1]

        # Remove common prefixes
        prefixes_to_remove = [
            "Translation:",
            "Translated:",
            "Here is the translation:",
            "The translation is:",
        ]
        for prefix in prefixes_to_remove:
            if response.lower().startswith(prefix.lower()):
                response = response[len(prefix) :].strip()

        return response
