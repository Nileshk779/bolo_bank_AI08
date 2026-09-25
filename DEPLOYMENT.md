# Deploying BoloBank

BoloBank runs two ways. Both use the same code; the difference is configuration.

| | Laptop / demo | Production stack |
|---|---|---|
| Start | `uvicorn main:app` + `npm run dev` | `docker compose up -d --build` |
| Database | SQLite file `backend/bolobank.db` | PostgreSQL |
| Rate limits & caches | In each process's memory | Shared in Redis |
| Scheduled jobs | Inside the API (`SCHEME_AUTO_UPDATE=true`) | Separate `worker` container |
| Web | Vite dev server | nginx serving the built app, proxying `/api` |
| Capacity | 1 process | `API_REPLICAS` containers behind nginx |

Nothing below is needed for the laptop setup.

## Production stack (Docker)

1. **Secrets.** `backend/.env` must exist with at least `GROQ_API_KEY` and a long random
   `SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`). Turn **off**
   `ENABLE_PASSWORD_LOGIN` and `SEED_DEMO_STAFF` and use Google sign-in
   (`GOOGLE_CLIENT_ID`, `AUTHORIZED_EMPLOYEE_EMAILS`) for real staff.
2. **Stack settings.** `cp .env.example .env` next to `docker-compose.yml` and set
   `POSTGRES_PASSWORD`.
3. **Start.** `docker compose up -d --build`, then open http://localhost:8080.
   Order: PostgreSQL and Redis → `migrate` (applies database migrations once) →
   `api` × `API_REPLICAS` and `worker` → `web`.
4. **Check.** `curl http://localhost:8080/api/health/ready` returns `"ready"` when the
   database and Redis are reachable.

### Scaling
* More API capacity: `docker compose up -d --scale api=4` (or raise `API_REPLICAS`).
  Each API container holds the embedding model (~0.5–1 GB RAM).
* Measure before and after with `python backend/tests/loadtest.py --base-url http://localhost:8080`
  (for a pure capacity test set `RATE_LIMIT_ENABLED=false`; everything comes from one IP).
* The limiting factor is usually the AI provider (Groq rate limits and cost), not the servers.
  Watch `bolobank_ai_calls_total{outcome="error"}` and the answer-cache hit rate.

### HTTPS (required for the microphone)
Browsers only allow microphone access on HTTPS (or `localhost`). Put TLS in front of the
`web` container, for example:
* a cloud load balancer with a managed certificate, forwarding to port 8080, or
* Caddy on the host: `your-domain.example { reverse_proxy localhost:8080 }` (gets and renews
  Let's Encrypt certificates automatically).

Then set `CORS_ORIGINS=https://your-domain.example` in `backend/.env`.

### Database migrations
* After changing `backend/database/models.py`:
  `cd backend && alembic revision --autogenerate -m "what changed"` — review the generated
  file in `migrations/versions/`, commit it. The test `tests/test_migrations.py` fails if a
  model change has no migration.
* Deploys apply them via the `migrate` service (`alembic upgrade head`).
* The laptop setup applies them automatically at startup (`AUTO_MIGRATE=true`). An existing
  `bolobank.db` from before migrations is recognised and recorded as up to date, keeping its data.

### Moving the demo data into PostgreSQL
With the stack running (so the schema exists and is empty), publish PostgreSQL temporarily
or run from a container on the same network, then:

```
python -m database.copy_sqlite_to_postgres --from bolobank.db \
    --to postgresql+psycopg://bolobank:PASSWORD@localhost:5432/bolobank
```

### Backups
PostgreSQL data lives in the `pgdata` volume. Back it up regularly, e.g.
`docker compose exec db pg_dump -U bolobank bolobank > backup.sql`, and test restoring it.
Redis holds only caches and rate-limit counters — nothing that needs a backup.

### Monitoring
* `GET /metrics` on each API container (Prometheus format): requests and response times
  per endpoint, AI calls/errors/response time, tokens, cache hits, rate-limit refusals.
  It is not exposed through the web proxy; set `METRICS_TOKEN` to require a token as well.
* `GET /api/health` (alive) and `GET /api/health/ready` (database and Redis reachable).
* Logs are JSON lines in the stack (`LOG_FORMAT=json`): `docker compose logs -f api worker`.

### Knowledge base and scheme data
`backend/data/*.json` are built into the image. After editing them, rebuild:
`docker compose up -d --build api worker`.

## Still to do before real customer data
* Replace gTTS (unofficial, not for commercial volume) with a supported speech service
  (e.g. Bhashini, Google Cloud Text-to-Speech or Azure) — `services/tts_service.py`.
* Role-based access (e.g. only managers approve schemes or see Branch Insights).
* Keep data in India, a data-processing agreement with the AI provider, retention rules,
  and an independent security review.
