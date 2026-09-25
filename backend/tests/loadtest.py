"""
Load test for the BoloBank API — measures throughput and response times.

    python tests/loadtest.py --users 50 --duration 30
    python tests/loadtest.py --ai --ai-requests 20        # small, capped real-AI run

Default mode costs nothing: each simulated customer starts a session, opens
the new-schemes list, runs an eligibility check and asks off-topic questions
(the confidence gate answers those without calling the AI, but they still
exercise the search model, database writes and session handling).

--ai sends real banking questions (Groq charges apply — capped by
--ai-requests). Questions repeat on purpose so the answer cache is exercised.

Rate limits: all simulated users come from one IP address, so for a
capacity test start the server with RATE_LIMIT_ENABLED=false. With limits on,
429 responses are counted separately — that is the limiter working.

Not a pytest file (no test_ prefix); run it against a running server.
"""
import argparse
import asyncio
import random
import statistics
import time
from collections import defaultdict

import httpx

OFF_TOPIC = ["what is the weather today", "who won the cricket match", "tell me a joke", "best movie this week"]
BANK_QUESTIONS = [
    ("mr", "बँक किती वाजता उघडते?"), ("mr", "माझे पासबुक हरवले, काय करू?"), ("hi", "एटीएम कार्ड खो गया है क्या करें"),
    ("hi", "पेंशन खाते में नहीं आई"), ("en", "what is the minimum balance for a savings account"), ("kn", "ಬ್ಯಾಂಕ್ ಎಷ್ಟು ಗಂಟೆಗೆ ತೆರೆಯುತ್ತದೆ?"),
]


class Stats:
    def __init__(self):
        self.times = defaultdict(list)
        self.errors = defaultdict(int)
        self.limited = defaultdict(int)

    def add(self, name, seconds, status):
        if status == 429:
            self.limited[name] += 1
        elif status >= 400 or status == 0:
            self.errors[name] += 1
        else:
            self.times[name].append(seconds)

    def report(self, elapsed):
        print(f"\n{'endpoint':28s} {'ok':>6s} {'errors':>7s} {'429s':>6s} {'req/s':>7s} {'p50 ms':>8s} {'p95 ms':>8s} {'max ms':>8s}")
        total_ok = 0
        for name in sorted(set(self.times) | set(self.errors) | set(self.limited)):
            t = sorted(self.times[name])
            total_ok += len(t)
            p = (lambda q: f"{t[min(len(t) - 1, int(q * len(t)))] * 1000:8.0f}") if t else (lambda q: f"{'-':>8s}")
            print(f"{name:28s} {len(t):6d} {self.errors[name]:7d} {self.limited[name]:6d} {len(t) / elapsed:7.1f} "
                  f"{p(0.5)} {p(0.95)} {(max(t) * 1000 if t else 0):8.0f}")
        print(f"\nTotal: {total_ok} successful requests in {elapsed:.1f}s = {total_ok / elapsed:.1f} req/s; "
              f"errors: {sum(self.errors.values())}; rate-limited: {sum(self.limited.values())}")


async def timed(stats, name, coro):
    start = time.perf_counter()
    try:
        r = await coro
        stats.add(name, time.perf_counter() - start, r.status_code)
        return r
    except httpx.HTTPError:
        stats.add(name, time.perf_counter() - start, 0)
        return None


async def customer(client, stats, deadline, rng):
    while time.perf_counter() < deadline:
        lang = rng.choice(["mr", "hi", "kn", "te", "en"])
        r = await timed(stats, "POST /customer/session/start", client.post("/api/customer/session/start", json={"language": lang}))
        if not r or r.status_code != 200:
            await asyncio.sleep(0.5)
            continue
        s = r.json()
        auth = {"Authorization": f"Bearer {s['customer_token']}"}
        await timed(stats, "GET  /customer/new-schemes", client.get(f"/api/customer/new-schemes?language={lang}"))
        await timed(stats, "POST /customer/eligibility", client.post("/api/customer/eligibility", headers=auth, json={
            "session_id": s["session_id"], "assets": {"gold_grams": rng.choice([10, 20, 50])}, "occupation": "farmer",
            "purpose": "farming", "age": rng.choice([30, 50, 68])}))
        for _ in range(2):
            await timed(stats, "POST /customer/chat (no AI)", client.post("/api/customer/chat", headers=auth, json={
                "session_id": s["session_id"], "text": rng.choice(OFF_TOPIC), "language": lang}))


async def ai_customer(client, stats, budget, rng):
    r = await client.post("/api/customer/session/start", json={"language": "mr"})
    s = r.json()
    auth = {"Authorization": f"Bearer {s['customer_token']}"}
    while budget["left"] > 0:
        budget["left"] -= 1
        lang, q = rng.choice(BANK_QUESTIONS)
        await timed(stats, "POST /customer/chat (AI)", client.post("/api/customer/chat", headers=auth, json={
            "session_id": s["session_id"], "text": q, "language": lang}))


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--users", type=int, default=20, help="simulated customers at the same time")
    ap.add_argument("--duration", type=float, default=20, help="seconds (default mode)")
    ap.add_argument("--ai", action="store_true", help="send real banking questions (Groq cost)")
    ap.add_argument("--ai-requests", type=int, default=20, help="total real AI questions in --ai mode")
    args = ap.parse_args()

    stats, rng = Stats(), random.Random(1)
    limits = httpx.Limits(max_connections=args.users * 2, max_keepalive_connections=args.users * 2)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=60, limits=limits) as client:
        (await client.get("/api/health")).raise_for_status()
        start = time.perf_counter()
        if args.ai:
            budget = {"left": args.ai_requests}
            print(f"AI mode: {args.ai_requests} real questions, {args.users} at a time …")
            await asyncio.gather(*(ai_customer(client, stats, budget, rng) for _ in range(min(args.users, args.ai_requests))))
        else:
            print(f"{args.users} simulated customers for {args.duration:g}s against {args.base_url} …")
            deadline = start + args.duration
            await asyncio.gather(*(customer(client, stats, deadline, random.Random(i)) for i in range(args.users)))
        stats.report(time.perf_counter() - start)


if __name__ == "__main__":
    asyncio.run(main())
