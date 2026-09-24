"""
Central AI Orchestrator.

Coordinates the individual AI services for both customer-facing chat and
the employee Copilot — it does not implement retrieval, generation, risk
rules, translation-parsing, account lookups, or privacy filtering itself;
each stays owned by its own service module.

                    AIOrchestrator
                          │
     ┌───────────────┬────┼────┬───────────────┐
     ↓                ↓         ↓               ↓
AccountService   RAGService  RiskService    LLMService
(mock account   (rag_service)(risk_service)(llm_service)
 data + intent
 detection)
     └───────────────┴────┼────┴───────────────┘
                          ↓
                 Response Pipeline
   (TranslationService + source attribution + confidence +
    ResponsePrivacyService — spoken_response / visual_data / sensitive)
                          │
             ┌────────────┴────────────┐
             ↓                         ↓
       Customer Mode              Employee Mode
  handle_customer_query()   handle_employee_query()

Two response paths, both ending in the same privacy-aware shape
(reply text + spoken_response + visual_data + sensitive):

  1. Account-data intent (e.g. "what's my balance?") — detected by
     AccountService before retrieval/generation even run. These never go
     through RAG/LLM at all: there's no real account data for the LLM to
     be grounded in, so a demo account is looked up directly and the
     Response Privacy Layer splits it into a safe spoken phrase + a
     screen-only `visual_data` payload. OTP/PIN/CVV/Aadhaar-PAN intents
     have no value to look up at all — the assistant explains it can't
     disclose these, spoken and shown identically, since there's nothing
     to hide beyond the refusal itself.

  2. Ordinary policy question — goes through semantic RAG + LLM as before,
     then the grounded reply is passed through the Response Privacy
     Layer's regex-based defense-in-depth pass, in case the LLM's answer
     unexpectedly contains something sensitive-looking (it shouldn't,
     since it's grounded only in static policy documents with no real
     customer data, but this is the safety net that catches it if it
     does).

Human-in-the-loop is preserved unchanged: this orchestrator only ever
produces text/structured display data — it has no capability to execute a
banking action, transfer funds, or change account state. RiskService flags
requests that touch security/money-movement so the response visibly says a
staff member must handle it; that framing is the entire mechanism, since
the AI was never able to act in the first place.
"""
import json
import logging

from services import account_service, response_privacy_service, risk_service, translation_service
from services.llm_service import COMPLEXITY_INSTRUCTIONS, LANGUAGE_NAMES, chat_completion
from services.rag_service import build_context, grounding_fallback, is_confident, retriever

logger = logging.getLogger("bolobank.orchestrator")


def _run_retrieval(query: str) -> dict:
    """RAGService call + source-attribution/confidence bookkeeping shared by
    both customer and employee modes."""
    results = retriever.retrieve(query)
    grounded = is_confident(results)
    return {
        "grounded": grounded,
        "context": build_context(results) if grounded else "",
        "sources": [
            {"topic": r.chunk.topic, "doc_id": r.chunk.doc_id, "chunk_index": r.chunk.chunk_index, "score": round(r.score, 3)}
            for r in results
        ]
        if grounded
        else [],
        "confidence": round(results[0].score, 3) if results else None,
    }


class AIOrchestrator:
    """Single entry point other layers (API routers) should use for any
    AI-backed response generation, so retrieval + risk + generation +
    translation + account-data + privacy logic is never duplicated across
    routes."""

    # ------------------------------------------------------------------ #
    # Shared: account-data intents (balance, account number, transaction,
    # card number, OTP, PIN, CVV, Aadhaar/PAN)
    # ------------------------------------------------------------------ #
    def _account_intent_response(self, text: str, intent: str, language: str) -> dict:
        """Mode-agnostic core for when the query is asking for specific
        account data. Returns a dict with generic keys; handle_customer_query
        / handle_employee_query adapt them to their own response shape."""
        risk = risk_service.assess(text)

        if intent in account_service.NEVER_DISCLOSE_INTENTS:
            phrase = response_privacy_service.cannot_disclose_phrase(language)
            phrase_en = response_privacy_service.cannot_disclose_phrase("en")
            return {
                "text_local": phrase,
                "text_english": phrase_en,
                "spoken_response": phrase,
                "visual_data": None,
                "sensitive": True,
                "risk_level": "high",
                "requires_human_review": True,
                "understood_summary": f"Customer is asking for their {intent.upper()}, which the assistant can never disclose.",
                "relevant_info": "OTP/PIN/CVV/ID numbers are never stored or retrievable by this system, for security.",
                "suggested_action": (
                    "Explain this can't be shared through the assistant. Verify the customer's identity yourself "
                    "if they need a reset or a secure channel to receive it."
                ),
            }

        account = account_service.get_demo_account()
        visual_data = account_service.build_visual_data(intent, account)
        phrase = response_privacy_service.screen_only_phrase(language)
        phrase_en = response_privacy_service.screen_only_phrase("en")
        return {
            "text_local": phrase,
            "text_english": phrase_en,
            "spoken_response": phrase,
            "visual_data": visual_data,
            "sensitive": True,
            "risk_level": risk.level,
            "requires_human_review": risk.requires_human_review,
            "understood_summary": f"Customer is asking for their {intent.replace('_', ' ')}.",
            "relevant_info": f"Demo account data ({intent}) — show the value on screen, never read it aloud.",
            "suggested_action": "Show the customer the value on screen; do not read the sensitive value aloud.",
        }

    # ------------------------------------------------------------------ #
    # Customer Mode
    # ------------------------------------------------------------------ #
    def handle_customer_query(self, text: str, language: str, complexity: str) -> dict:
        intent = account_service.detect_account_intent(text)
        if intent:
            shared = self._account_intent_response(text, intent, language)
            return {
                "reply_local": shared["text_local"],
                "reply_english": shared["text_english"],
                "spoken_response": shared["spoken_response"],
                "visual_data": shared["visual_data"],
                "sensitive": shared["sensitive"],
                "sources": [],
                "confidence": None,
                "grounded": False,
                "risk_level": shared["risk_level"],
                "requires_human_review": shared["requires_human_review"],
            }

        retrieval = _run_retrieval(text)
        risk = risk_service.assess(text)
        return self._run_customer_pipeline(text, language, complexity, retrieval, risk)

    def _run_customer_pipeline(self, text: str, language: str, complexity: str, retrieval: dict, risk) -> dict:
        if not retrieval["grounded"]:
            # Anti-hallucination hard gate (see rag_service.is_confident):
            # no confident context -> never call the LLM, return the fixed
            # grounded fallback instead.
            reply_local = grounding_fallback(language)
            reply_english = grounding_fallback("en")
        else:
            raw = self._generate_customer_completion(text, retrieval["context"], language, complexity)
            reply_local, reply_english = translation_service.split_local_and_english(raw)

        protected = response_privacy_service.protect_for_speech(reply_local, language=language)

        return {
            "reply_local": reply_local,
            "reply_english": reply_english,
            "spoken_response": protected.safe_text,
            "visual_data": None,
            "sensitive": protected.redacted,
            "sources": retrieval["sources"],
            "confidence": retrieval["confidence"],
            "grounded": retrieval["grounded"],
            "risk_level": risk.level,
            "requires_human_review": risk.requires_human_review,
        }

    def _generate_customer_completion(self, text: str, context: str, language: str, complexity: str) -> str:
        lang_name = LANGUAGE_NAMES.get(language, "Hindi")
        complexity_instruction = COMPLEXITY_INSTRUCTIONS.get(complexity, COMPLEXITY_INSTRUCTIONS["simple"])
        system_prompt = (
            "You are BoloBank, a warm and patient banking assistant speaking with a customer "
            "at an Indian bank branch. Only use the bank policy context given below — never "
            "invent numbers, fees, or rules, and never state anything not directly supported "
            "by the context. Each context passage is labeled with its source; you do not need "
            "to cite sources in your reply, but do not go beyond what they say. If the context "
            "doesn't fully cover the question, say so plainly and suggest the customer speak "
            "with a staff member rather than guessing. You have no access to this customer's "
            "real account data (balances, transactions, card details) — if asked, say so; you "
            "are never the source of a real personal balance or account number.\n\n"
            f"Explanation style: {complexity_instruction}\n\n"
            f"Bank policy context (top-matching passages only, not the full knowledge base):\n{context}\n\n"
            f"Reply in {lang_name}. After your reply, on a new line starting with 'EN:', give a "
            "short English translation for the staff member to read."
        )
        return chat_completion(system_prompt, text, max_tokens=400)

    # ------------------------------------------------------------------ #
    # Employee Mode (Copilot)
    # ------------------------------------------------------------------ #
    def handle_employee_query(self, query: str, language: str, complexity: str) -> dict:
        intent = account_service.detect_account_intent(query)
        if intent:
            shared = self._account_intent_response(query, intent, language)
            return {
                "understood_summary": shared["understood_summary"],
                "relevant_info": shared["relevant_info"],
                "suggested_action": shared["suggested_action"],
                "suggested_reply_local": shared["text_local"],
                "suggested_reply_english": shared["text_english"],
                "spoken_response": shared["spoken_response"],
                "visual_data": shared["visual_data"],
                "sensitive": shared["sensitive"],
                "sources": [],
                "confidence": None,
                "grounded": False,
                "risk_level": shared["risk_level"],
                "requires_human_review": shared["requires_human_review"],
            }

        retrieval = _run_retrieval(query)
        risk = risk_service.assess(query)
        return self._run_employee_pipeline(query, language, complexity, retrieval, risk)

    def _run_employee_pipeline(self, query: str, language: str, complexity: str, retrieval: dict, risk) -> dict:
        if not retrieval["grounded"]:
            fallback = grounding_fallback(language)
            fallback_en = grounding_fallback("en")
            return {
                "understood_summary": "Customer's question does not clearly match any known policy.",
                "relevant_info": "No knowledge-base passage matched this query with enough confidence to brief on.",
                "suggested_action": "Verify manually with the employee handbook or escalate to a supervisor before responding.",
                "suggested_reply_local": fallback,
                "suggested_reply_english": fallback_en,
                "spoken_response": fallback,
                "visual_data": None,
                "sensitive": False,
                "sources": [],
                "confidence": retrieval["confidence"],
                "grounded": False,
                "risk_level": risk.level,
                "requires_human_review": True,
            }

        parsed = self._generate_employee_completion(query, retrieval["context"], language, complexity)

        # Risk framing: a flagged request gets the human-review note
        # prepended to the suggested action, regardless of what the LLM
        # itself suggested — this is decided by RiskService, not left to
        # the model to remember to mention.
        suggested_action = parsed["suggested_action"]
        if risk.requires_human_review:
            suggested_action = f"{risk.note} {suggested_action}".strip()

        protected = response_privacy_service.protect_for_speech(parsed["reply_local"], language=language)

        return {
            "understood_summary": parsed["understood_summary"],
            "relevant_info": parsed["relevant_info"],
            "suggested_action": suggested_action,
            "suggested_reply_local": parsed["reply_local"],
            "suggested_reply_english": parsed["reply_english"],
            "spoken_response": protected.safe_text,
            "visual_data": None,
            "sensitive": protected.redacted,
            "sources": retrieval["sources"],
            "confidence": retrieval["confidence"],
            "grounded": True,
            "risk_level": risk.level,
            "requires_human_review": risk.requires_human_review,
        }

    def _generate_employee_completion(self, query: str, context: str, language: str, complexity: str) -> dict:
        lang_name = LANGUAGE_NAMES.get(language, "Hindi")
        complexity_instruction = COMPLEXITY_INSTRUCTIONS.get(complexity, COMPLEXITY_INSTRUCTIONS["simple"])

        system_prompt = (
            "You are an AI copilot for a bank branch employee (not the customer). The "
            "employee has a customer in front of them asking a question, possibly in a "
            "regional Indian language. Your job is to brief the employee quickly and "
            "accurately, and to draft (never send) a customer-facing reply they can review, "
            "edit, and approve.\n\n"
            "Only use the bank policy context given below — never invent numbers, fees, or "
            "rules, and never state anything not directly supported by the context. Each "
            "context passage is labeled with its source. If the context doesn't fully cover "
            "the question, say so plainly in understood_summary/relevant_info rather than "
            "guessing.\n\n"
            f"Bank policy context (top-matching passages only, not the full knowledge base):\n{context}\n\n"
            f"Draft reply style: {complexity_instruction}\n\n"
            "Respond with ONLY a JSON object (no markdown fences, no extra text) with "
            "exactly these keys:\n"
            '  "understood_summary": one short sentence in English restating what the '
            "customer wants.\n"
            '  "relevant_info": 2-4 short bullet points (as a single string, '
            "newline-separated) of the relevant policy facts the employee needs.\n"
            '  "suggested_action": one concrete next step the employee should take '
            "(e.g. which form to pull up, what document to ask for, whether to escalate).\n"
            f'  "reply_local": a customer-facing reply written in {lang_name}, following '
            "the draft reply style above.\n"
            '  "reply_english": the English translation of reply_local, for the employee '
            "to double-check before it's spoken aloud."
        )

        raw = chat_completion(system_prompt, query, max_tokens=500, json_mode=True)

        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError:
            logger.warning("Copilot LLM response was not valid JSON, falling back to empty fields")
            parsed = {}

        return {
            "understood_summary": (parsed.get("understood_summary") or "").strip(),
            "relevant_info": (parsed.get("relevant_info") or "").strip(),
            "suggested_action": (parsed.get("suggested_action") or "").strip(),
            "reply_local": (parsed.get("reply_local") or "").strip(),
            "reply_english": (parsed.get("reply_english") or "").strip(),
        }


# Single shared instance — routers use this.
ai_orchestrator = AIOrchestrator()


# --- Backward-compatible free functions -------------------------------- #
# Kept as thin delegating wrappers so existing callers/tests written before
# this consolidation keep working without change. New code should prefer
# ai_orchestrator.handle_customer_query()/handle_employee_query() directly,
# since those also expose sources/confidence/risk/spoken_response/
# visual_data that these wrappers don't.
def generate_customer_reply(text: str, language: str, complexity: str) -> dict:
    result = ai_orchestrator.handle_customer_query(text, language, complexity)
    return {"reply_local": result["reply_local"], "reply_english": result["reply_english"]}


def generate_copilot_briefing(query: str, language: str, complexity: str) -> dict:
    result = ai_orchestrator.handle_employee_query(query, language, complexity)
    return {
        "understood_summary": result["understood_summary"],
        "relevant_info": result["relevant_info"],
        "suggested_action": result["suggested_action"],
        "suggested_reply_local": result["suggested_reply_local"],
        "suggested_reply_english": result["suggested_reply_english"],
    }
