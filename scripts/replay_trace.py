"""Seeded replay harness for verifying deterministic analysis results."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from refinery.core.orchestrator import create_orchestrator
from refinery.utils.config import config


def _json_default(obj: Any) -> Any:
    from enum import Enum

    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj):
        return asdict(obj)
    return str(obj)


async def _run_single(
    trace_id: str,
    project: str,
    expected: str,
    codebase: str,
    seed: int | None,
    run_index: int,
    output_dir: Path,
    with_hypothesis: bool,
) -> Dict[str, Any]:
    if seed is not None:
        config.analysis_seed = seed

    progress_events: List[Dict[str, Any]] = []

    def progress_callback(event_type: str, payload: Dict[str, Any]) -> None:
        progress_events.append(
            {
                "timestamp": time.time(),
                "event": event_type,
                "payload": payload,
            }
        )

    orchestrator = await create_orchestrator(
        codebase, progress_callback=progress_callback
    )

    analysis = await orchestrator.analyze_failure(
        trace_id=trace_id,
        project=project,
        expected_behavior=expected,
    )

    stage_metadata = orchestrator.failure_analyst.get_stage_metadata()
    run_metadata = orchestrator.get_run_metadata()

    hypotheses: List[Dict[str, Any]] = []
    if with_hypothesis:
        generated = await orchestrator.generate_fixes(analysis.diagnosis)
        hypotheses = [asdict(hyp) for hyp in generated]

        events_path = output_dir / f"hypothesis_events_run_{run_index}.jsonl"
        with events_path.open("w", encoding="utf-8") as events_file:
            for event in progress_events:
                events_file.write(json.dumps(event, default=_json_default) + "\n")

    run_payload = {
        "analysis": {
            "trace_analysis": asdict(analysis.trace_analysis),
            "gap_analysis": asdict(analysis.gap_analysis),
            "diagnosis": asdict(analysis.diagnosis),
        },
        "stage_metadata": stage_metadata,
        "run_metadata": run_metadata,
        "hypotheses": hypotheses,
        "hypothesis_events": progress_events if with_hypothesis else [],
    }

    output_path = output_dir / f"run_{run_index}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(run_payload, f, indent=2, default=_json_default)

    return run_payload


def _hash_change(change: Dict[str, Any]) -> Optional[str]:
    new_content = change.get("new_content")
    if not isinstance(new_content, str):
        return None
    return hashlib.sha256(new_content.encode("utf-8")).hexdigest()


def _compute_diff_summary(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not runs:
        return {}

    base_json = json.dumps(runs[0]["analysis"], sort_keys=True, default=_json_default)
    mismatches = 0

    stage_keys = ["stage1", "stage2", "stage3", "stage4"]
    chunk_sets = []
    fetch_counts = []

    for run in runs:
        current_json = json.dumps(
            run["analysis"], sort_keys=True, default=_json_default
        )
        if current_json != base_json:
            mismatches += 1

        stage_meta = run.get("stage_metadata", {})
        stage1_meta = stage_meta.get("stage1", {})
        chunk_sets.append(set(stage1_meta.get("retrieved_chunk_ids", [])))

        run_meta = run.get("run_metadata", {})
        fetch_counts.append(run_meta.get("langsmith_fetch_count"))

    chunk_overlap = 0.0
    if chunk_sets:
        intersection = (
            set.intersection(*chunk_sets) if len(chunk_sets) > 1 else chunk_sets[0]
        )
        union = set.union(*chunk_sets) if len(chunk_sets) > 1 else chunk_sets[0]
        chunk_overlap = len(intersection) / len(union) if union else 1.0

    hypothesis_counts = [len(run.get("hypotheses") or []) for run in runs]
    hypothesis_hashes = [
        [
            _hash_change(change)
            for hyp in run.get("hypotheses") or []
            for change in hyp.get("proposed_changes") or []
            if _hash_change(change)
        ]
        for run in runs
    ]

    return {
        "json_diff_rate": mismatches / max(len(runs) - 1, 1),
        "chunk_id_overlap": chunk_overlap,
        "langsmith_fetch_counts": fetch_counts,
        "stage_metadata_snapshot": {
            key: runs[0].get("stage_metadata", {}).get(key) for key in stage_keys
        },
        "hypothesis_counts": hypothesis_counts,
        "hypothesis_change_hashes": hypothesis_hashes,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic replay harness")
    parser.add_argument("trace_id", help="LangSmith trace identifier")
    parser.add_argument("--project", required=True, help="LangSmith project name")
    parser.add_argument(
        "--expected", required=True, help="Expected behavior description"
    )
    parser.add_argument("--codebase", default=".", help="Path to analyzed codebase")
    parser.add_argument(
        "--runs", type=int, default=3, help="Number of iterations to execute"
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="Seed for deterministic decoding"
    )
    parser.add_argument(
        "--output-dir", default="baseline_reports", help="Directory to store outputs"
    )
    parser.add_argument(
        "--with-hypothesis",
        action="store_true",
        help="Generate hypotheses during replay and capture progress events",
    )

    args = parser.parse_args()

    output_root = Path(args.output_dir) / args.trace_id
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"Running {args.runs} replays for trace {args.trace_id}...")

    runs: List[Dict[str, Any]] = []
    for run_idx in range(1, args.runs + 1):
        print(f"→ Replay {run_idx}/{args.runs}")
        result = await _run_single(
            trace_id=args.trace_id,
            project=args.project,
            expected=args.expected,
            codebase=args.codebase,
            seed=args.seed,
            run_index=run_idx,
            output_dir=output_root,
            with_hypothesis=args.with_hypothesis,
        )
        runs.append(result)

    summary = _compute_diff_summary(runs)
    summary_path = output_root / "diff_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=_json_default)

    print("Replay summary saved to", summary_path)
    print(json.dumps(summary, indent=2, default=_json_default))


if __name__ == "__main__":
    asyncio.run(main())
