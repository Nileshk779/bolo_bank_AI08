"""
Retrieval quality evaluation with the REAL embedding model (not a pytest
test — the unit tests mock embeddings). Run from backend/:

    python tests/eval_rag.py

Uses data/rag_eval_questions.json: reworded questions that do not appear
in the knowledge base, in English, Hinglish, Hindi, Marathi, Kannada and
Telugu, plus off-topic questions that must NOT be answered confidently.
Compares retrieval over the answer text only vs. answer text + example
questions, and sweeps the confidence threshold.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import rag_service  # noqa: E402
from services.rag_service import SemanticRetriever  # noqa: E402

EVAL_PATH = Path(__file__).resolve().parent.parent / "data" / "rag_eval_questions.json"


def evaluate(retriever: SemanticRetriever, items: list[dict], threshold: float) -> dict:
    in_scope = [i for i in items if i["expected"]]
    off_topic = [i for i in items if not i["expected"]]
    top1 = top3 = answered_right = answered_wrong = 0
    misses = []
    for item in in_scope:
        results = retriever.retrieve(item["q"])
        ids = [r.chunk.doc_id for r in results]
        confident = bool(results) and results[0].score >= threshold
        top1 += ids[:1] == [item["expected"]]
        top3 += item["expected"] in ids
        if confident and ids[0] == item["expected"]:
            answered_right += 1
        elif confident:
            answered_wrong += 1
        if ids[:1] != [item["expected"]] or not confident:
            misses.append((item["q"], item["expected"], ids[0] if ids else None, round(results[0].score, 3) if results else None))
    false_confident = sum(1 for i in off_topic if (r := retriever.retrieve(i["q"])) and r[0].score >= threshold)
    return {
        "n": len(in_scope),
        "top1": top1 / len(in_scope),
        "top3": top3 / len(in_scope),
        "answered_right": answered_right / len(in_scope),
        "answered_wrong": answered_wrong / len(in_scope),
        "off_topic_answered": f"{false_confident}/{len(off_topic)}",
        "misses": misses,
    }


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else EVAL_PATH
    items = json.loads(path.read_text(encoding="utf-8"))["questions"]
    modes = {
        "answers only": SemanticRetriever(index_example_questions=False, lexical_weight=0),
        "+ example questions": SemanticRetriever(index_example_questions=True, lexical_weight=0),
        "+ questions + keywords 0.2": SemanticRetriever(index_example_questions=True, lexical_weight=0.2),
        "+ questions + keywords 0.3": SemanticRetriever(index_example_questions=True, lexical_weight=0.3),
        "+ questions + keywords 0.4": SemanticRetriever(index_example_questions=True, lexical_weight=0.4),
    }
    print(f"{len(items)} eval questions; current MIN_CONFIDENCE = {rag_service.MIN_CONFIDENCE}\n")
    for name, retriever in modes.items():
        for threshold in (0.3, 0.35, 0.38, 0.42, 0.45, 0.5):
            m = evaluate(retriever, items, threshold)
            print(
                f"{name:28s} thr={threshold:.2f}  top1={m['top1']:.0%}  top3={m['top3']:.0%}  "
                f"answered correctly={m['answered_right']:.0%}  answered WRONG={m['answered_wrong']:.0%}  "
                f"off-topic answered={m['off_topic_answered']}"
            )
        print()
    m = evaluate(SemanticRetriever(), items, rag_service.MIN_CONFIDENCE)
    print("Misses / not confident (current settings):")
    for q, exp, got, score in m["misses"]:
        print(f"  expected {exp} got {got} score={score}  |  {q}")


if __name__ == "__main__":
    main()
