"""
Low-level LLM client wrapper shared by ai_orchestrator.py and
copilot_service.py, plus the language/complexity vocabulary that used to be
duplicated between /chat and /copilot in the original main.py.
"""
import logging
import threading
import time
from contextvars import ContextVar

from core.config import settings
from core.exceptions import UpstreamServiceError
from services import metrics

logger = logging.getLogger("bolobank.llm")

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "mr": "Marathi",
    "te": "Telugu",
    "kn": "Kannada",
    "en": "English",
}

# "Explain Like I'm 60" — complexity presets that reshape how the AI explains
# banking concepts, aimed at elderly / low-literacy customers.
COMPLEXITY_INSTRUCTIONS = {
    "simple": (
        "Explain like you're talking to a 60-year-old customer with no banking or "
        "financial background. Use very short sentences (under 12 words each). Avoid "
        "all jargon — no words like 'interest rate', 'reducing balance', 'KYC', etc. "
        "without immediately explaining them in plain everyday language with a small "
        "example. Use warm, respectful, patient tone, like a helpful grandchild "
        "explaining something to a grandparent."
    ),
    "normal": (
        "Explain clearly and politely, as you would to an adult customer with some "
        "everyday familiarity with banking. You can use standard banking terms, but "
        "briefly clarify any term a first-time customer might not know."
    ),
    "detailed": (
        "Give a precise, complete explanation suitable for a customer who wants full "
        "detail — include exact terms, relevant numbers from the policy context, and "
        "any conditions or exceptions that apply."
    ),
}


# Token usage for the current request, for the branch dashboard's cost
# figures (services/analytics_service.py). A request handler calls
# start_usage_tracking(); every chat_completion() in that request adds to it.
_usage: ContextVar[dict | None] = ContextVar("llm_usage", default=None)


def start_usage_tracking() -> None:
    _usage.set({"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0})


def tracked_usage() -> dict:
    return dict(_usage.get() or {"llm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0})


def _record_usage(completion) -> None:
    acc = _usage.get()
    usage = getattr(completion, "usage", None)
    if usage:
        metrics.AI_TOKENS.labels("prompt").inc(getattr(usage, "prompt_tokens", 0) or 0)
        metrics.AI_TOKENS.labels("completion").inc(getattr(usage, "completion_tokens", 0) or 0)
    if acc is None:
        return
    acc["llm_calls"] += 1
    if usage:
        acc["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        acc["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0


_client = None
_client_lock = threading.Lock()


def _get_groq_client():
    """One shared client per process: it keeps a connection pool, so calls
    reuse connections instead of opening a new one each time."""
    global _client
    if not settings.GROQ_API_KEY:
        raise UpstreamServiceError("Groq", "GROQ_API_KEY is not set on the server")
    if _client is None:
        with _client_lock:
            if _client is None:
                from groq import Groq

                _client = Groq(api_key=settings.GROQ_API_KEY, timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=settings.LLM_MAX_RETRIES)
    return _client


def chat_completion(system_prompt: str, user_text: str, max_tokens: int = 500, json_mode: bool = False) -> str:
    """Shared low-level call used by both the customer chat orchestrator and
    the copilot service — was duplicated as two near-identical Groq calls
    (with the client re-constructed each time) in the original main.py."""
    client = _get_groq_client()
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]
    models = [settings.GROQ_CHAT_MODEL]
    if settings.GROQ_FALLBACK_MODEL and settings.GROQ_FALLBACK_MODEL != settings.GROQ_CHAT_MODEL:
        models.append(settings.GROQ_FALLBACK_MODEL)

    last_exc = None
    for model in models:
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if model.startswith("openai/gpt-oss"):
            # Reasoning models: keep hidden reasoning short so answers are fast
            # and the reasoning doesn't use up max_tokens before the reply.
            kwargs["reasoning_effort"] = "low"
        started = time.perf_counter()
        try:
            completion = client.chat.completions.create(model=model, max_tokens=max_tokens, messages=messages, **kwargs)
        except Exception as exc:  # groq raises its own types; the SDK has already retried
            logger.error("Groq chat completion failed on %s: %s", model, exc)
            metrics.AI_CALLS.labels(model, "error").inc()
            last_exc = exc
            continue
        metrics.AI_CALLS.labels(model, "ok").inc()
        metrics.AI_SECONDS.labels(model).observe(time.perf_counter() - started)
        if model != settings.GROQ_CHAT_MODEL:
            logger.warning("Answered with fallback model %s", model)
        _record_usage(completion)
        return completion.choices[0].message.content or ""

    raise UpstreamServiceError("Groq LLM", str(last_exc)) from last_exc


def transcribe_audio(file_path, language: str | None) -> str:
    client = _get_groq_client()
    try:
        with open(file_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                language=language if language and language != "auto" else None,
            )
    except Exception as exc:
        logger.error("Groq transcription failed: %s", exc)
        raise UpstreamServiceError("Groq Whisper", str(exc)) from exc

    return result.text
