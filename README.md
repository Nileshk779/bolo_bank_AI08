# BoloBank

Voice-first, multilingual AI banking assistant for elderly and low-literacy
customers, with an AI Copilot for bank employees. The AI assists staff and
customers — it never replaces a human employee, and it has no capability to
execute any banking action.

> **Read this first:** this project has a **production-oriented
> architecture** — it's organized, tested, and reasoned about the way a real
> system would be. It is **not production-deployment-ready**. See
> [Production-oriented architecture vs. actual production readiness](#production-oriented-architecture-vs-actual-production-readiness)
> before deploying it anywhere real customer data would touch it.

---

## Contents

- [Architecture](#architecture)
- [Setup](#setup)
- [Environment variables](#environment-variables)
- [Google Authentication](#google-authentication)
- [Semantic RAG](#semantic-rag)
- [AI Orchestrator](#ai-orchestrator)
- [Elderly Voice Mode](#elderly-voice-mode)
- [Privacy-Aware Voice Disclosure](#privacy-aware-voice-disclosure)
- [Security considerations](#security-considerations)
- [Running tests](#running-tests)
- [Production-oriented architecture vs. actual production readiness](#production-oriented-architecture-vs-actual-production-readiness)
- [Known limitations](#known-limitations)

---

## Architecture

```
React Frontend (Vite)
        │  REST (/api/...)
        ▼
FastAPI Modular Monolith
  api/          — routes only (parse request, call orchestrator/service, return response)
  auth/         — password + Google sign-in, JWT sessions
  database/     — SQLAlchemy models + session
  schemas/      — Pydantic request/response models
  core/         — config, logging, exception handling
        │
        ▼
AI Orchestrator (services/ai_orchestrator.py)
  ├── AccountService     — demo account data + sensitive-intent detection
  ├── RAGService          — semantic retrieval (embeddings + cosine similarity)
  ├── RiskService          — rule-based risk framing (money-movement/security terms)
  ├── LLMService            — Groq LLM (chat) + Whisper (speech-to-text)
  ├── TranslationService     — local-language/English reply parsing
  └── ResponsePrivacyService  — sensitive-value redaction (structured + regex defense-in-depth)
        │
        ▼
SQLite (staff, queue-adjacent, audit turns) · Groq API · gTTS
```

No microservices — this is a deliberate architectural choice, not a
shortcut. A hackathon-scale knowledge base and single-branch deployment
don't need service-to-service network calls; a modular monolith with clean
internal boundaries gets the same separation-of-concerns benefit with far
less operational complexity, and every internal boundary (`RAGService`,
`RiskService`, etc.) is already shaped so it *could* become a separate
service later if the system ever needed to scale that way.

### Backend layout

```
backend/
├── main.py                  FastAPI app: logging, DB init, CORS, exception handlers, routers
├── api/                     Routes — auth, chat, copilot, voice, sessions, queue, health
├── auth/                    security.py (JWT/password), google_auth.py, seed.py
├── database/                session.py (engine), models.py (Staff, Turn)
├── schemas/                 Pydantic models per domain
├── core/                    config.py, logging.py, exceptions.py
├── services/
│   ├── ai_orchestrator.py       Central orchestrator — customer + employee modes
│   ├── account_service.py       DEMO account data + intent detection (see below)
│   ├── rag_service.py           Chunking, semantic retrieval, grounding gate
│   ├── vector_store.py          In-memory cosine-similarity store (pgvector/Qdrant-ready interface)
│   ├── embedding_service.py     sentence-transformers wrapper
│   ├── llm_service.py           Groq chat + Whisper wrapper
│   ├── risk_service.py          Rule-based risk classification
│   ├── translation_service.py   Local/English reply parsing
│   ├── response_privacy_service.py  Sensitive-value redaction (the privacy layer)
│   ├── tts_service.py           gTTS wrapper
│   ├── speech_service.py        Upload handling + Whisper call
│   ├── session_service.py       Turn logging + structured summary generation
│   └── queue_service.py         In-memory token queue
├── knowledge_base.json      Static bank policy documents (the RAG corpus)
├── tests/                   pytest suite (see "Running tests")
├── requirements.txt         Runtime dependencies
└── requirements-dev.txt     Test-only dependencies
```

### Frontend layout

```
frontend/
└── src/
    ├── App.jsx                Tab router, session lifecycle
    ├── api.js                 Fetch wrapper, auth token storage
    └── components/
        ├── LoginPage.jsx       Password login + "Continue with Google"
        ├── CustomerPanel.jsx   Voice loop + Elderly Voice Mode
        ├── CopilotPanel.jsx    Employee query → briefing → reviewable draft reply
        ├── QueuePanel.jsx      Token queue, elderly priority lane
        ├── SessionSummary.jsx  Structured employee-facing summary
        ├── VisualDataCard.jsx  Screen-only display for sensitive data
        └── MicButton.jsx       Hold-to-speak recorder
```

---

## Setup

**Backend**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # fill in GROQ_API_KEY at minimum
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env      # only needed if enabling Google sign-in
npm run dev
```

Password login and demo staff seeding are disabled by default. For a local or controlled hackathon demo only, set `ENABLE_PASSWORD_LOGIN=true` and `SEED_DEMO_STAFF=true`; this seeds `staff` / `bolobank123`. Never enable demo seeding in production.

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | **Yes** | Powers both LLM chat replies (Llama 3.3) and speech transcription (Whisper). Free at [console.groq.com/keys](https://console.groq.com/keys). |
| `SECRET_KEY` | **Yes in production** | Signs staff session JWTs. Production startup fails if the development fallback is used. |
| `CORS_ORIGINS` | No (default: `http://localhost:5173`) | Comma-separated allowed frontend origins. |
| `TOKEN_TTL_HOURS` | No (default: `12`) | Staff session token lifetime. |
| `ENVIRONMENT` | No (default: `development`) | Set to `production` to enable production startup safety checks. |
| `ENABLE_PASSWORD_LOGIN` | No (default: `false`) | Enables legacy username/password login for local/demo use only. |
| `SEED_DEMO_STAFF` | No (default: `false`) | Seeds `staff` / `bolobank123` only when explicitly enabled; forbidden in production. |
| `LOG_LEVEL` | No (default: `INFO`) | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR`. |
| `GOOGLE_CLIENT_ID` | No | Enables Google Sign-In for staff. Leave blank to disable. |
| `GOOGLE_ALLOWED_DOMAIN` | No | Optional extra restriction — only accept Google accounts on this email domain. |
| `AUTHORIZED_EMPLOYEE_EMAILS` | Required if using Google sign-in | Comma-separated employee emails allowed to sign in with Google. See [Google Authentication](#google-authentication). |
| `DATABASE_PATH` | No | Overrides the SQLite file path — used by the test suite for isolation, not needed for normal use. |

### Frontend (`frontend/.env`)

| Variable | Required | Purpose |
|---|---|---|
| `VITE_GOOGLE_CLIENT_ID` | Only if using Google sign-in | Must match the backend's `GOOGLE_CLIENT_ID`. Public value — safe to ship to the browser (Google Identity Services requires this; no client *secret* exists in this flow). |

---

## Google Authentication

Staff (not customers — see below) can sign in with a "Continue with Google"
button alongside the original username/password form (kept for local
development and as a fallback).

**Flow:** React (Google Identity Services) → Google ID token → backend
verifies the token server-side (signature, issuer, audience, expiry, via
the `google-auth` library) → checks the verified email against an
**authorized-employee allowlist** → issues BoloBank's own JWT, identical in
shape to a password-login token.

**The authorized-employee mechanism:** signing in with Google **never**
auto-creates a staff account. An employee's email must already exist as a
`Staff` row — provisioned by listing it in `AUTHORIZED_EMPLOYEE_EMAILS` at
server startup — before their Google account is trusted. Once they sign in
successfully, their Google account's stable subject ID is bound to that
row; a different Google account later claiming the same email is rejected.

**Setup:**
1. Google Cloud Console → APIs & Services → Credentials → Create OAuth
   Client ID → type "Web application" → add your frontend origin under
   "Authorized JavaScript origins". No redirect URI needed.
2. Set `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend)
   to the same value.
3. Set `AUTHORIZED_EMPLOYEE_EMAILS` to your staff's email addresses.

**Customers never need a Google account** — they don't authenticate at all.
The interaction model is: a staff member logs in (password or Google),
hands the device to the customer, and the customer speaks. The customer's
identity verification is the staff member being physically present, exactly
as in the original design — Google Auth changes nothing about that.

---

## Semantic RAG

Replaces the original keyword-overlap retrieval with real embedding-based
search.

- **Embedding model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  — compact (~118MB), multilingual (built on XLM-RoBERTa, 100-language
  pretraining), runs on CPU. Officially benchmarked for Hindi/English
  paraphrase similarity; Marathi/Telugu/Kannada are in the base model's
  pretraining data but weren't specifically paraphrase-tuned (see
  [Known limitations](#known-limitations)).
- **Chunking:** greedy sentence-boundary chunking, ~350 characters/chunk,
  1-sentence overlap between consecutive chunks of the same document.
- **Vector store:** in-memory, numpy-backed cosine similarity
  (`services/vector_store.py`), behind a `BaseVectorStore` interface —
  swapping in pgvector/Qdrant later means implementing that interface, not
  touching any caller.
- **Top-K:** 3.
- **Grounding / anti-hallucination:** a hard confidence gate
  (`MIN_CONFIDENCE = 0.38`). Below this, the LLM is **never called** — the
  orchestrator returns a fixed "I couldn't confidently find this, please
  ask a staff member" response in the customer's language. This is
  code-enforced, not a prompt instruction the model could ignore.
- **Source attribution:** every response includes `sources` (topic,
  document ID, chunk index, similarity score) and a `confidence` value.

---

## AI Orchestrator

A single coordination layer (`services/ai_orchestrator.py`) for both
customer chat and the employee Copilot, eliminating the duplicated
retrieval/LLM wiring the two flows used to have independently.

```
                AIOrchestrator
                      │
    ┌─────────────────┼─────────────────┐
    ↓                 ↓                 ↓
RAGService        RiskService        LLMService
    └─────────────────┼─────────────────┘
                      ↓
             Response Pipeline
  (TranslationService + source attribution + confidence +
   ResponsePrivacyService — spoken_response / visual_data / sensitive)
                      │
         ┌────────────┴────────────┐
         ↓                         ↓
   Customer Mode              Employee Mode
```

Two response paths converge on the same privacy-aware shape:
1. **Account-data intent** (e.g. "what's my balance?") — detected before
   retrieval/generation even run; the LLM is skipped entirely since there's
   no real account data for it to be grounded in.
2. **Ordinary policy question** — semantic RAG + LLM, then the grounded
   reply passes through the privacy layer's defense-in-depth pass.

**Human-in-the-loop:** the orchestrator only ever produces text/structured
display data. It has no capability to execute a banking action, transfer
funds, or change account state — so there is nothing for a human to be "in
the loop" of bypassing. `RiskService` flags security/money-movement
requests so the response visibly defers to a staff member; that framing is
the entire mechanism, because the AI was never able to act in the first
place.

---

## Elderly Voice Mode

A toggle in the Customer Panel, designed for voice-first interaction with
minimal reading:

- Large mic button, large 🔊 **LISTEN AGAIN**, ✅ **YES**, ❌ **NO** controls
- Forces `complexity=simple` (short sentences, no unexplained jargon)
- Slower, clearer TTS pace (`slow=True` in gTTS)
- Sensitive data shown as a large, clearly-labeled card, never buried in
  paragraph text

---

## Privacy-Aware Voice Disclosure

**Core rule: sensitive financial information is never sent to TTS, under
any circumstance.**

Treated as sensitive: account balance, account number, transaction
amounts, OTP, PIN, CVV, card number, Aadhaar/PAN, and similar personal
identifiers.

Account numbers are masked on-screen by default (only the last four digits are shown); exact values are never sent to TTS.

**Response shape** (`ChatResponse` / `CopilotResponse`):
```json
{
  "reply_local": "...",
  "spoken_response": "Your current available balance is displayed securely on the screen.",
  "visual_data": { "type": "balance", "label": "Current Available Balance", "value": "12450", "currency": "INR" },
  "sensitive": true
}
```
The frontend sends only `spoken_response` to `/api/speak`. The raw value
lives in exactly one place — `visual_data` — and is never interpolated
into any string that could reach TTS.

**Two layers, both real (not stubs):**
1. **Structured** — `services/account_service.py` provides a small,
   clearly-labeled **demo/mock** account (this app has no real
   core-banking integration). Balance/account-number/transaction/card-number
   queries are answered with a generic spoken phrase + a screen-only
   `visual_data` payload. **OTP/PIN/CVV/Aadhaar/PAN are never looked up or
   displayed at all** — there's no "show it differently" for these; the
   assistant explains why and defers to a staff member.
2. **Defense-in-depth** — `services/response_privacy_service.py` regex-scans
   any free-form LLM output for sensitive-looking patterns before it's
   allowed near TTS. `POST /api/speak` runs this **unconditionally, with no
   bypass flag** — every call is filtered, regardless of what the caller
   claims about the text already being safe.

Generic policy figures (e.g. "the minimum balance requirement is Rs.
1,000") are deliberately **not** redacted — only personal-possessive
phrasing ("your balance", "my account") near a number triggers the filter,
so the assistant stays useful for genuine policy questions.

---

## Security considerations

**What's in place:**
- Passwords hashed with PBKDF2-HMAC-SHA256 (100k iterations)
- JWT sessions (HS256), same token shape regardless of login method
- Google ID tokens verified server-side (signature, issuer, audience,
  expiry) — the frontend never sends an email directly; it's derived only
  from verified token claims
- All non-public routes require a valid Bearer token (`get_current_staff`)
- CORS restricted to explicit configured origins, not wildcarded
- No secrets or API keys reach the frontend — only the public Google
  Client ID (which Google Identity Services requires to be public)
- Uploaded audio filenames are never used as-is in a filesystem path (fixed
  during the final security review — see below); only a server-generated
  UUID + an allow-listed extension
- Unhandled exceptions return a generic message to the client; the real
  error is logged server-side only, never leaked in the response
- Synthesized TTS audio files are deleted immediately after being served
  (and cleaned up on synthesis failure too), rather than accumulating
  indefinitely on disk

**Issues found and fixed in the final review pass:**
- **Path traversal in file upload** (`services/speech_service.py`): the
  on-disk filename was built directly from the client-supplied filename.
  Fixed to discard it entirely except for a validated extension.
- **Disk-space leak** (`api/voice.py`, `services/tts_service.py`):
  synthesized audio was never deleted after serving, and a failed gTTS
  call could leave an orphaned empty file behind. Both fixed, with
  regression tests.

**Known gaps (see [Known limitations](#known-limitations)):**
customer speech is redacted for sensitive values before audit storage
(only the AI-generated summary is); no rate limiting on login or
LLM-calling endpoints; no upload size limit; no per-staff session
ownership/RBAC (any authenticated staff member can view any session).

---

## Running tests

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

**81 tests**, covering: Google auth (valid/unauthorized/invalid/expired/missing
token, protected routes, account binding), semantic RAG (exact/paraphrase/
multilingual/irrelevant/no-match/multi-document retrieval, chunking, vector
math), the AI Orchestrator (risk flagging, source attribution, confidence,
customer vs. employee modes), the privacy layer (all 5 required disclosure
scenarios × 5 languages, defense-in-depth, the no-bypass guarantee),
structured session summaries, voice pipeline (all 5 languages, elderly
slow-speech), and the two security fixes above.

**Important caveat:** this sandboxed development environment has no network
access to `huggingface.co` (blocks the real embedding model download) or
Google/Groq's APIs. Tests that depend on those exercise our own
orchestration/logic with mocked model calls — they validate that retrieval
ranking, confidence gating, redaction, and response assembly are wired
correctly, **not** the real embedding model's semantic quality or live
Google/Groq behavior. Verify those specifically in an environment with real
network access before depending on this in production.

---

## Production-oriented architecture vs. actual production readiness

This project is built the way a production system would be structured —
layered architecture, dependency injection via FastAPI, a real (if simple)
test suite, structured logging, centralized config, a genuine privacy
layer — **and that is different from being ready to deploy with real
customer data.** Specifically, before any real deployment, you would still
need to:

- Replace the demo `account_service.py` with a real core-banking
  integration, with proper per-customer authentication (this app currently
  shows the *same* demo account to every session)
- Move off SQLite to a production database with migrations (no Alembic or
  equivalent exists yet — schema changes require manual intervention)
- Add rate limiting (login attempts, LLM-calling endpoints)
- Add per-staff authorization/RBAC (currently: any authenticated staff
  member can access any session or perform any staff action equally)
- Get the real embedding model's multilingual quality independently
  verified (see [Known limitations](#known-limitations))
- Have the machine-assisted translations (grounding fallbacks, privacy
  disclosure phrases) reviewed by native speakers
- Run a real penetration test / security audit — the review in this
  project was a focused pass against a specific checklist, not a
  professional audit
- Define and enforce a real data-retention policy for privacy-filtered audit transcripts (see below)

---

## Known limitations

- **Demo account data**: `account_service.get_demo_account()` returns one
  hardcoded fake account for every session — there is no real per-customer
  banking data anywhere in this system.
- **Embedding model quality unverified in this environment**: real
  semantic quality (especially for Marathi/Telugu/Kannada, which the
  embedding model wasn't specifically paraphrase-tuned for) needs
  verification with real network access, which this development sandbox
  didn't have.
- **Machine-assisted translations**: grounding-fallback and
  privacy-disclosure phrases in Hindi/Marathi/Telugu/Kannada are
  AI-translated, not reviewed by native speakers.
- **Audit transcript redaction is regex-based**: sensitive-looking account/card numbers and context-linked amounts are filtered before storage, and summaries are filtered again. A real deployment still needs a formal data-retention policy and stronger structured PII/DLP controls.
- **No rate limiting** on login or LLM-calling endpoints.
- **No upload size limit** on audio uploads.
- **In-memory queue**: resets on restart, not safe across multiple worker
  processes (a deliberate scoping decision from an earlier phase — kept
  in-memory rather than DB-backed specifically to avoid a behavior change
  during a structural-only refactor).
- **No RBAC**: every authenticated staff member has identical permissions
  and can view any session.
- **Risk classification is keyword-based**, not ML — proportionate given
  the app has no action-execution capability regardless of classification
  accuracy.

## Separate customer and staff portals

The frontend now begins with explicit role selection:

- **Customer Portal** — no staff controls are shown. The customer first selects Marathi, Hindi, Kannada, Telugu or English; after that, the complete customer UI (headings, buttons, status messages, errors, privacy notices and conversation labels) stays in that language. Customer sessions use a short-lived customer token separate from employee authentication.
- **Staff Portal** — authenticated employee-only workspace for assisted sessions, bilingual transcripts, queue management, AI Copilot and structured session summaries.

This separation keeps the customer experience simple and accessible while retaining operational tools for employees.
