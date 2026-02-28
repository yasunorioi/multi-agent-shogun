#!/usr/bin/env python3
"""
audit_grading.py - CLI for grading.json-compatible audit scoring.

Manages rubric-based audit gradings (0-3 per aspect, 5 aspects, 15pt max).
Stores results in data/audit_gradings/{subtask_id}_{auditor}.json.

Usage:
    python3 scripts/audit_grading.py save \
        --subtask subtask_XXX --auditor ohariko \
        --completeness 3 --accuracy 2 --formatting 3 --consistency 2 --cross 2 \
        [--evidence-file /tmp/evidence.json] [--cmd cmd_XXX] [--worker ashigaru1]

    python3 scripts/audit_grading.py show subtask_XXX [--auditor ohariko]

    python3 scripts/audit_grading.py list [--worker ashigaru1] [--auditor ohariko] \
        [--verdict approved] [--limit 10] [--json]

    python3 scripts/audit_grading.py benchmark [--period 30d] [--json]
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
GRADINGS_DIR = PROJECT_ROOT / "data" / "audit_gradings"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ASPECTS = ["completeness", "accuracy", "formatting", "consistency", "cross_consistency"]
ASPECT_LABELS = {
    "completeness": "完全性",
    "accuracy": "正確性",
    "formatting": "書式",
    "consistency": "一貫性",
    "cross_consistency": "横断一貫性",
}
ASPECT_TEXTS = {
    "completeness": "要求された内容が全て含まれている",
    "accuracy": "事実誤認・技術的な間違いがない",
    "formatting": "フォーマット・命名規則は適切",
    "consistency": "他のドキュメント・コードとの整合性がある",
    "cross_consistency": "類似タスク・過去監査との横断一貫性がある",
}

# Thresholds: (min_score, verdict)  -- checked in order, first match wins
THRESHOLDS_15 = [
    (12, "approved"),
    (8, "conditional_approved"),
    (5, "rejected_trivial"),
    (0, "rejected_judgment"),
]
THRESHOLDS_12 = [
    (10, "approved"),
    (7, "conditional_approved"),
    (4, "rejected_trivial"),
    (0, "rejected_judgment"),
]

VERDICT_LABELS = {
    "approved": "合格",
    "conditional_approved": "条件付き合格",
    "rejected_trivial": "要修正（自明）",
    "rejected_judgment": "要修正（要判断）",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def determine_verdict(total_score: int, max_score: int) -> str:
    thresholds = THRESHOLDS_15 if max_score == 15 else THRESHOLDS_12
    for min_score, verdict in thresholds:
        if total_score >= min_score:
            return verdict
    return "rejected_judgment"


def load_evidence(path: str) -> dict:
    """Load optional evidence JSON file (claims + per-aspect evidence)."""
    p = Path(path)
    if not p.exists():
        print(f"Warning: evidence file not found: {path}", file=sys.stderr)
        return {}
    with open(p) as f:
        return json.load(f)


def build_grading(
    subtask_id: str,
    auditor: str,
    scores: dict[str, int],
    evidence: dict | None = None,
    cmd_id: str | None = None,
    worker_id: str | None = None,
) -> dict:
    """Build a grading.json-compatible dict from scores."""
    evidence = evidence or {}
    aspect_evidence = evidence.get("aspects", {})
    claims = evidence.get("claims", [])

    # Determine if cross_consistency is included
    has_cross = scores.get("cross_consistency") is not None
    active_aspects = ASPECTS if has_cross else ASPECTS[:4]
    max_score = 15 if has_cross else 12

    expectations = []
    aspects_summary = {}
    total_score = 0

    for aspect in active_aspects:
        score = scores[aspect]
        total_score += score
        aspects_summary[aspect] = score
        expectations.append({
            "aspect": aspect,
            "text": ASPECT_TEXTS[aspect],
            "score": score,
            "passed": score >= 2,
            "evidence": aspect_evidence.get(aspect, ""),
        })

    verdict = determine_verdict(total_score, max_score)
    score_rate = round(total_score / max_score, 2)

    grading = {
        "subtask_id": subtask_id,
        "auditor": auditor,
        "timestamp": now_iso(),
        "kousatsu_ok": has_cross,
        "expectations": expectations,
        "summary": {
            "total_score": total_score,
            "max_score": max_score,
            "score_rate": score_rate,
            "verdict": verdict,
            "aspects": aspects_summary,
        },
    }

    if cmd_id:
        grading["cmd_id"] = cmd_id
    if worker_id:
        grading["worker_id"] = worker_id
    if claims:
        grading["claims"] = claims

    return grading


def save_grading(grading: dict) -> Path:
    """Save grading to data/audit_gradings/{subtask_id}_{auditor}.json."""
    GRADINGS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{grading['subtask_id']}_{grading['auditor']}.json"
    filepath = GRADINGS_DIR / filename
    with open(filepath, "w") as f:
        json.dump(grading, f, indent=2, ensure_ascii=False)
    return filepath


def find_gradings(
    subtask_id: str | None = None,
    auditor: str | None = None,
    worker_id: str | None = None,
    verdict: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search gradings in data/audit_gradings/."""
    if not GRADINGS_DIR.exists():
        return []

    results = []
    # Sort by modification time (newest first)
    files = sorted(GRADINGS_DIR.glob("subtask_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    for filepath in files:
        if subtask_id and not filepath.name.startswith(subtask_id):
            continue
        if auditor and f"_{auditor}.json" not in filepath.name:
            continue

        with open(filepath) as f:
            data = json.load(f)

        if worker_id and data.get("worker_id") != worker_id:
            continue
        if verdict and data.get("summary", {}).get("verdict") != verdict:
            continue

        results.append(data)
        if len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_save(args: argparse.Namespace) -> None:
    scores = {
        "completeness": args.completeness,
        "accuracy": args.accuracy,
        "formatting": args.formatting,
        "consistency": args.consistency,
    }

    # cross_consistency is optional (None when kousatsu NG)
    if args.cross is not None:
        scores["cross_consistency"] = args.cross

    evidence = None
    if args.evidence_file:
        evidence = load_evidence(args.evidence_file)

    grading = build_grading(
        subtask_id=args.subtask,
        auditor=args.auditor,
        scores=scores,
        evidence=evidence,
        cmd_id=args.cmd,
        worker_id=args.worker,
    )

    filepath = save_grading(grading)
    summary = grading["summary"]
    v = VERDICT_LABELS.get(summary["verdict"], summary["verdict"])
    print(f"Saved: {filepath.name}")
    print(f"Score: {summary['total_score']}/{summary['max_score']} ({summary['score_rate']:.0%}) → {v}")


def cmd_show(args: argparse.Namespace) -> None:
    results = find_gradings(subtask_id=args.subtask_id, auditor=args.auditor)
    if not results:
        print(f"No grading found for {args.subtask_id}", file=sys.stderr)
        sys.exit(1)

    for grading in results:
        if args.json:
            print(json.dumps(grading, indent=2, ensure_ascii=False))
        else:
            s = grading["summary"]
            v = VERDICT_LABELS.get(s["verdict"], s["verdict"])
            print(f"=== {grading['subtask_id']} ({grading['auditor']}) ===")
            print(f"Timestamp: {grading['timestamp']}")
            if grading.get("cmd_id"):
                print(f"Cmd: {grading['cmd_id']}")
            if grading.get("worker_id"):
                print(f"Worker: {grading['worker_id']}")
            print(f"Kousatsu: {'OK' if grading.get('kousatsu_ok') else 'NG'}")
            print(f"Score: {s['total_score']}/{s['max_score']} ({s['score_rate']:.0%})")
            print(f"Verdict: {v}")
            print()
            for exp in grading["expectations"]:
                label = ASPECT_LABELS.get(exp["aspect"], exp["aspect"])
                mark = "PASS" if exp["passed"] else "FAIL"
                print(f"  [{mark}] {label}: {exp['score']}/3")
                if exp.get("evidence"):
                    print(f"         {exp['evidence']}")
            if grading.get("claims"):
                print()
                print("  Claims:")
                for c in grading["claims"]:
                    mark = "OK" if c["verified"] else "NG"
                    print(f"    [{mark}] {c['claim']}")
                    if c.get("evidence"):
                        print(f"         {c['evidence']}")
        print()


def cmd_list(args: argparse.Namespace) -> None:
    results = find_gradings(
        auditor=args.auditor,
        worker_id=args.worker,
        verdict=args.verdict,
        limit=args.limit,
    )

    if not results:
        print("No gradings found.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    fmt = "{:<16s} {:<10s} {:<12s} {:>5s}  {:<16s} {:<20s}"
    print(fmt.format("subtask_id", "auditor", "worker", "score", "verdict", "timestamp"))
    print("-" * 85)
    for g in results:
        s = g["summary"]
        v = VERDICT_LABELS.get(s["verdict"], s["verdict"])
        score_str = f"{s['total_score']}/{s['max_score']}"
        print(fmt.format(
            g["subtask_id"],
            g["auditor"],
            g.get("worker_id", "-"),
            score_str,
            v,
            g["timestamp"],
        ))


def cmd_benchmark(args: argparse.Namespace) -> None:
    """Basic statistics from accumulated gradings (Phase 1 stub)."""
    all_gradings = find_gradings(limit=9999)

    # Filter by period
    if args.period:
        period_str = args.period.rstrip("d")
        try:
            days = int(period_str)
        except ValueError:
            print(f"Invalid period: {args.period}. Use format like '30d'.", file=sys.stderr)
            sys.exit(1)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        all_gradings = [g for g in all_gradings if g["timestamp"] >= cutoff]

    if not all_gradings:
        print("No gradings found for benchmark.", file=sys.stderr)
        sys.exit(1)

    # Aggregate
    total_count = len(all_gradings)
    verdict_counts: dict[str, int] = {}
    aspect_totals: dict[str, list[int]] = {a: [] for a in ASPECTS}
    auditor_counts: dict[str, int] = {}

    for g in all_gradings:
        s = g["summary"]
        verdict = s["verdict"]
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        auditor_counts[g["auditor"]] = auditor_counts.get(g["auditor"], 0) + 1
        for aspect, score in s.get("aspects", {}).items():
            if aspect in aspect_totals:
                aspect_totals[aspect].append(score)

    stats = {
        "total_gradings": total_count,
        "period": args.period or "all",
        "verdict_distribution": verdict_counts,
        "aspect_averages": {
            a: round(sum(scores) / len(scores), 2) if scores else None
            for a, scores in aspect_totals.items()
        },
        "auditor_counts": auditor_counts,
    }

    if args.json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    print(f"=== Benchmark ({stats['period']}) ===")
    print(f"Total gradings: {total_count}")
    print()
    print("Verdict distribution:")
    for v, count in sorted(verdict_counts.items()):
        label = VERDICT_LABELS.get(v, v)
        pct = count / total_count * 100
        print(f"  {label}: {count} ({pct:.0f}%)")
    print()
    print("Aspect averages (0-3):")
    for aspect, scores in aspect_totals.items():
        label = ASPECT_LABELS.get(aspect, aspect)
        if scores:
            avg = sum(scores) / len(scores)
            print(f"  {label}: {avg:.2f} (n={len(scores)})")
        else:
            print(f"  {label}: - (no data)")
    print()
    print("Auditor counts:")
    for auditor, count in sorted(auditor_counts.items()):
        print(f"  {auditor}: {count}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="audit_grading.py - grading.json compatible audit scoring CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- save ---
    p_save = sub.add_parser("save", help="Save a grading result")
    p_save.add_argument("--subtask", required=True, help="subtask_XXX")
    p_save.add_argument("--auditor", required=True, choices=["ohariko", "ginmiyaku"])
    p_save.add_argument("--completeness", type=int, required=True, choices=range(4), metavar="0-3")
    p_save.add_argument("--accuracy", type=int, required=True, choices=range(4), metavar="0-3")
    p_save.add_argument("--formatting", type=int, required=True, choices=range(4), metavar="0-3")
    p_save.add_argument("--consistency", type=int, required=True, choices=range(4), metavar="0-3")
    p_save.add_argument("--cross", type=int, default=None, choices=range(4), metavar="0-3",
                         help="Cross-consistency score (omit if kousatsu NG)")
    p_save.add_argument("--evidence-file", help="Path to evidence JSON file")
    p_save.add_argument("--cmd", help="cmd_XXX")
    p_save.add_argument("--worker", help="Worker ID (e.g. ashigaru1)")

    # --- show ---
    p_show = sub.add_parser("show", help="Show grading for a subtask")
    p_show.add_argument("subtask_id", help="subtask_XXX")
    p_show.add_argument("--auditor", help="Filter by auditor")
    p_show.add_argument("--json", action="store_true")

    # --- list ---
    p_list = sub.add_parser("list", help="List gradings")
    p_list.add_argument("--worker", help="Filter by worker ID")
    p_list.add_argument("--auditor", help="Filter by auditor")
    p_list.add_argument("--verdict", help="Filter by verdict")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--json", action="store_true")

    # --- benchmark ---
    p_bench = sub.add_parser("benchmark", help="Aggregate statistics (Phase 1 stub)")
    p_bench.add_argument("--period", default=None, help="Period like '30d'")
    p_bench.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "save":
        cmd_save(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)


if __name__ == "__main__":
    main()
