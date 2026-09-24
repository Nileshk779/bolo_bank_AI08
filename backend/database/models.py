from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from database.session import Base


class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Password login (original MVP) — nullable so Google-only accounts don't
    # need a password.
    username = Column(String, unique=True, index=True)
    password_salt = Column(String)
    password_hash = Column(String)

    # Google Sign-In. `email` is the authorization key: an employee's email
    # must already be present here (provisioned via AUTHORIZED_EMPLOYEE_EMAILS,
    # see auth/seed.py) before their Google account is trusted — signing in
    # with Google never creates a new Staff row on its own. `google_sub` is
    # bound to the account on first successful sign-in and checked on every
    # subsequent one, so a future token for the same email but a different
    # Google account (e.g. after an email is reassigned) is rejected rather
    # than silently accepted.
    email = Column(String, unique=True, index=True, nullable=True)
    google_sub = Column(String, unique=True, index=True, nullable=True)

    display_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Turn(Base):
    """One line of a customer<->assistant conversation. Doubles as the audit log."""

    __tablename__ = "turns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    role = Column(String)  # "customer" or "assistant"
    language = Column(String)
    text_local = Column(Text)
    text_english = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SchemeDraft(Base):
    """A scheme picked up by the daily update job (services/scheme_update_service.py).

    Starts as "pending" and only reaches customers after an employee approves
    it — the AI extraction is never published on its own.
    """

    __tablename__ = "scheme_drafts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_id = Column(String, unique=True, index=True)
    title = Column(String)
    source_name = Column(String)
    source_url = Column(String, nullable=True)
    published_on = Column(String)  # ISO date from the feed
    raw_text = Column(Text)
    draft_json = Column(Text)  # the extracted scheme, same shape as loan_schemes.json entries
    extraction_method = Column(String)  # "llm" | "preset" | "preset_after_llm_error"
    validation_issues = Column(Text, default="[]")  # JSON list of strings
    status = Column(String, default="pending", index=True)  # pending | approved | rejected
    fetched_at = Column(DateTime, default=datetime.utcnow)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, nullable=True)


class SchemeUpdateRun(Base):
    """One execution of the daily scheme update job — evidence of when the
    catalogue was last checked, shown to staff."""

    __tablename__ = "scheme_update_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger = Column(String)  # "scheduled" | "manual"
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    items_seen = Column(Integer, default=0)
    new_drafts = Column(Integer, default=0)
    error = Column(Text, nullable=True)


class SchemeAlert(Base):
    """A newly approved scheme that matches an existing customer (with
    consent). Staff decide whether to contact the customer — nothing is sent
    automatically. See services/scheme_alert_service.py."""

    __tablename__ = "scheme_alerts"
    __table_args__ = (UniqueConstraint("scheme_id", "customer_id", name="uq_alert_scheme_customer"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    draft_id = Column(Integer, index=True)
    scheme_id = Column(String, index=True)
    scheme_name = Column(String)
    customer_id = Column(String, index=True)
    customer_name = Column(String)
    customer_age = Column(Integer)
    customer_branch = Column(String, nullable=True)
    language = Column(String)
    reasons_json = Column(Text)
    staff_checks_json = Column(Text, default="[]")
    message_local = Column(Text)
    message_english = Column(Text)
    status = Column(String, default="new", index=True)  # new | contacted | not_suitable
    created_at = Column(DateTime, default=datetime.utcnow)
    handled_by = Column(String, nullable=True)
    handled_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)


class InteractionEvent(Base):
    """One answered question or eligibility check, for the branch manager
    dashboard (services/analytics_service.py). Holds counts-level facts —
    topic, language, whether the AI answered or handed over to staff, token
    usage — not conversation content, except the (redacted) text of
    questions the AI could not answer, so the knowledge base can be improved.
    Rows with is_demo=True are generated sample data and can be removed."""

    __tablename__ = "interaction_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    kind = Column(String, index=True)  # "answer" | "eligibility"
    channel = Column(String)  # "customer_portal" | "staff_session" | "copilot"
    session_id = Column(String, index=True)
    language = Column(String)
    elderly_mode = Column(Integer, default=0)
    topic = Column(String, nullable=True)  # knowledge-base topic of the best source
    doc_id = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    answered_by_ai = Column(Integer, default=0)  # grounded answer, no human review needed
    handed_to_staff = Column(Integer, default=0)
    account_query = Column(Integer, default=0)  # balance/account-data question
    level_change = Column(String, nullable=True)  # "simpler" | "reexplain" | "more_detail"
    unanswered_text = Column(Text, nullable=True)  # redacted; only when not answered by AI
    assets_json = Column(Text, nullable=True)  # eligibility: which asset types the customer has
    matched_json = Column(Text, nullable=True)  # eligibility: matched scheme ids
    estimated_amount_inr = Column(Integer, nullable=True)  # eligibility: best loan estimate
    llm_calls = Column(Integer, default=0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    is_demo = Column(Integer, default=0, index=True)
