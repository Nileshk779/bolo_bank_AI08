"""
Translation handling for the customer chat flow.

Today this is a parser, not a translator: the generation LLM is asked to
produce the local-language reply and an 'EN:'-delimited English translation
in one completion, and this function splits them apart. That logic used to
live inline in ai_orchestrator.py as a bare string-split; extracting it here
gives "translation" a single owner the orchestrator coordinates rather than
reimplements, per the orchestration-layer goal.

The employee Copilot flow doesn't use this — it asks the LLM for structured
JSON with separate reply_local/reply_english keys directly, since that
output already needs JSON parsing for its other fields anyway.

A real standalone translation step (a dedicated translation model/API call,
independent of the generation LLM) is a reasonable future upgrade; this
module is the one place that change would land without touching callers.
"""


def split_local_and_english(raw_completion: str) -> tuple[str, str]:
    if "EN:" in raw_completion:
        local_part, english_part = raw_completion.split("EN:", 1)
    else:
        local_part, english_part = raw_completion, ""
    return local_part.strip(), english_part.strip()
