# BoloBank synthetic demo data

This folder contains synthetic data for the hackathon prototype only. No record represents a real bank customer.

Added demo endpoints:
- `GET /api/demo/customers`
- `GET /api/demo/customers/CUST001`
- `GET /api/demo/customers/CUST001/transactions`
- `GET /api/demo/queue`
- `GET /api/demo/sessions`

`bank_knowledge.json` is wired into the existing semantic RAG loader. Its schema is supported directly by `services/rag_service.py`.

Do not replace these records with real account numbers, Aadhaar/PAN data, OTPs, PINs, CVVs, card numbers, balances, or private banking information. The demo knowledge base is not a substitute for approved and current bank/RBI policy sources in production.
