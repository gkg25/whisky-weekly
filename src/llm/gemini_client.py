from __future__ import annotations
import json
import os
import random
import sys
import time
from typing import Optional

import google.generativeai as genai


DEFAULT_MODEL = "gemini-2.5-flash-lite"
RATE_LIMIT_MIN_INTERVAL = 5.0
MAX_RETRIES = 3
RATE_LIMIT_BACKOFF_BASE = 25.0


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, verbose: bool = False):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Configure .env or pass api_key explicitly.")
        genai.configure(api_key=api_key)
        self.model_name = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        self._model = genai.GenerativeModel(self.model_name)
        self._last_call_at = 0.0
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.verbose = verbose

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_call_at
        if elapsed < RATE_LIMIT_MIN_INTERVAL:
            time.sleep(RATE_LIMIT_MIN_INTERVAL - elapsed)

    def _track_usage(self, response) -> None:
        try:
            meta = response.usage_metadata
            self.total_input_tokens += getattr(meta, "prompt_token_count", 0) or 0
            self.total_output_tokens += getattr(meta, "candidates_token_count", 0) or 0
        except Exception:
            pass

    def generate_json(self, system_prompt: str, user_content: str) -> dict:
        prompt = f"{system_prompt}\n\n----\n\n{user_content}"
        last_err: Optional[Exception] = None
        is_rate = False
        for attempt in range(MAX_RETRIES + 1):
            self._wait_for_rate_limit()
            try:
                response = self._model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"},
                )
                self._last_call_at = time.monotonic()
                self.total_calls += 1
                self._track_usage(response)
                return json.loads(response.text)
            except json.JSONDecodeError as e:
                last_err = e
                is_rate = False
                if self.verbose:
                    print(f"  JSON parse error (attempt {attempt+1}): {e}", file=sys.stderr)
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                is_rate = "429" in msg or "quota" in msg or "rate" in msg or "resource_exhausted" in msg
                if self.verbose:
                    label = "rate-limited" if is_rate else "error"
                    print(f"  Gemini {label} (attempt {attempt+1}): {str(e)[:100]}", file=sys.stderr)
                if not is_rate and attempt >= 1:
                    break
            if attempt < MAX_RETRIES:
                if is_rate:
                    backoff = RATE_LIMIT_BACKOFF_BASE * (attempt + 1) + random.uniform(0, 5)
                else:
                    backoff = (2 ** attempt) + random.uniform(0, 0.8)
                if self.verbose:
                    print(f"    sleeping {backoff:.0f}s before retry", file=sys.stderr)
                time.sleep(backoff)
        raise RuntimeError(f"Gemini failed after {MAX_RETRIES+1} attempts: {last_err}")

    def usage_summary(self) -> dict:
        return {
            "model": self.model_name,
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }
