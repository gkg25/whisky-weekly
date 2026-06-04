from __future__ import annotations
import json
import os
import random
import re
import sys
import time
from typing import Optional

import google.generativeai as genai


DEFAULT_MODEL = "gemini-2.5-flash-lite"
RATE_LIMIT_MIN_INTERVAL_DEFAULT = 8.0
MAX_RETRIES = 2
PER_CALL_TIMEOUT = 60.0
BACKOFF_CAP = 30.0
_RETRY_AFTER_RE = re.compile(r"retry in\s+([\d.]+)\s*s", re.IGNORECASE)


def _extract_retry_after(err_msg: str) -> Optional[float]:
    m = _RETRY_AFTER_RE.search(err_msg)
    return float(m.group(1)) if m else None


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, verbose: bool = False):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Configure .env or pass api_key explicitly.")
        genai.configure(api_key=api_key)
        self.model_name = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        self._model = genai.GenerativeModel(self.model_name)
        env_interval = os.environ.get("GEMINI_RATE_INTERVAL")
        self.min_interval = float(env_interval) if env_interval else RATE_LIMIT_MIN_INTERVAL_DEFAULT
        self._last_call_at = 0.0
        self.total_calls = 0
        self.total_rate_limit_hits = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.verbose = verbose

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_call_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _track_usage(self, response) -> None:
        try:
            meta = response.usage_metadata
            self.total_input_tokens += getattr(meta, "prompt_token_count", 0) or 0
            self.total_output_tokens += getattr(meta, "candidates_token_count", 0) or 0
        except Exception:
            pass

    def _compute_backoff(self, attempt: int, err_msg: str, is_rate: bool) -> float:
        if is_rate:
            requested = _extract_retry_after(err_msg)
            if requested is not None:
                return min(BACKOFF_CAP, requested + 1.0) + random.uniform(0, 1.5)
            return min(BACKOFF_CAP, 15.0) + random.uniform(0, 1.5)
        return min(8.0, 2 ** attempt) + random.uniform(0, 0.5)

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
                    request_options={"timeout": PER_CALL_TIMEOUT},
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
                if is_rate:
                    self.total_rate_limit_hits += 1
                if self.verbose:
                    label = "rate-limited" if is_rate else "error"
                    print(f"  Gemini {label} (attempt {attempt+1}): {str(e)[:100]}", file=sys.stderr)
                if not is_rate and attempt >= 1:
                    break
            if attempt < MAX_RETRIES:
                backoff = self._compute_backoff(attempt, str(last_err) if last_err else "", is_rate)
                if self.verbose:
                    print(f"    sleeping {backoff:.1f}s before retry", file=sys.stderr)
                time.sleep(backoff)
        raise RuntimeError(f"Gemini failed after {MAX_RETRIES+1} attempts: {last_err}")

    def usage_summary(self) -> dict:
        return {
            "model": self.model_name,
            "total_calls": self.total_calls,
            "total_rate_limit_hits": self.total_rate_limit_hits,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }
