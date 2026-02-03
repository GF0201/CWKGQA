#!/usr/bin/env python3
"""KG smoke runner: load triples + index, run sanity checks, produce report.

Outputs suitable for paper "图谱构建与质量分析" section:
- metrics.json: kg_num_triples, kg_num_entities, kg_num_relations, kg_density
- artifacts/kg_sample_audit.csv: random sample for manual annotation
- artifacts/case_studies.md: sample preview
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import set_seed, DualLogger, write_repro_manifest, save_json, save_jsonl, load_json, save_metrics  # type: ignore

TASK_NAME = "task_kg_smoke"
AUDIT_SAMPLE_N = 100
CASE_STUDIES_N = 8


def _load_triples(path: Path) -> list[dict]:
    triples: list[dict] = []
    if path.suffix.lower() == ".tsv":
        import csv as csvmod
        with open(path, "r", encoding="utf-8") as f:
            r = csvmod.DictReader(f, delimiter="\t")
            for row in r:
                s = (row.get("subject") or row.get("head") or "").strip()
                p = (row.get("predicate") or row.get("connect") or "").strip()
                o = (row.get("object") or row.get("tail") or "").strip()
                triples.append({"subject": s, "predicate": p, "object": o})
    else:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                s = (obj.get("subject") or obj.get("head") or "").strip()
                p = (obj.get("predicate") or obj.get("connect") or "").strip()
                o = (obj.get("object") or obj.get("tail") or "").strip()
                triples.append({"subject": s, "predicate": p, "object": o})
    return triples


def _load_index(index_dir: Path, name: str) -> dict | None:
    p = index_dir / f"{name}.json"
    if not p.exists():
        return None
    return load_json(p)


def _collect_input_files(triples_path: Path, index_dir: Path) -> list[Path]:
    """Collect file paths for hashing (exclude dirs to avoid PermissionError)."""
    out = [triples_path]
    for name in ("forward.json", "backward.json", "hp_to_t.json"):
        p = index_dir / name
        if p.exists():
            out.append(p)
    return out


def main() -> tuple[int, str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--triples", type=str, required=True)
    parser.add_argument("--index_dir", type=str, required=True)
    parser.add_argument("--output-id", type=str, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--audit-n", type=int, default=AUDIT_SAMPLE_N, help="Number of triples to sample for audit")
    args = parser.parse_args()

    set_seed(args.seed)
    triples_path = Path(args.triples)
    index_dir = Path(args.index_dir)
    input_files = _collect_input_files(triples_path, index_dir)
    exp_id = args.output_id or f"kg_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / exp_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = DualLogger(run_dir, "run.log")
    start_time = datetime.now().isoformat()
    logger.log(f"argv: {' '.join(sys.argv)}")
    logger.log("KG smoke started")

    per_sample: list[dict] = []
    failures: list[dict] = []

    # Check 1: load triples
    try:
        triples = _load_triples(triples_path)
        n = len(triples)
        per_sample.append({
            "qid": "load_triples",
            "status": "ok",
            "question": "Load triples",
            "em": 1,
            "f1": 1,
            "error_type": "",
            "trace_path": "",
            "n_triples": n,
        })
        logger.log(f"Loaded {n} triples")

        # Compute KG metrics for paper "图谱构建与质量分析"
        entities = set(t["subject"] for t in triples) | set(t["object"] for t in triples)
        relations = set(t["predicate"] for t in triples)
        n_entities = len(entities)
        n_relations = len(relations)
        # density: directed graph, E / (V*(V-1)) or E/V^2 when V large
        density = n / max(1, n_entities * (n_entities - 1)) if n_entities > 1 else 0.0
        metrics = {
            "kg_num_triples": n,
            "kg_num_entities": n_entities,
            "kg_num_relations": n_relations,
            "kg_density": round(density, 6),
        }
        save_metrics(metrics, run_dir / "metrics.json")
        logger.log(f"Metrics: n_triples={n}, n_entities={n_entities}, n_relations={n_relations}, density={density:.6f}")
    except Exception as e:
        per_sample.append({
            "qid": "load_triples",
            "status": "fail",
            "question": "Load triples",
            "error_type": "load_error",
            "trace_path": "",
        })
        failures.append({"qid": "load_triples", "error_type": "load_error"})
        logger.log(f"FAIL load triples: {e}")
        end_time = datetime.now().isoformat()
        write_repro_manifest(
            run_dir,
            run_id=exp_id,
            start_time=start_time,
            end_time=end_time,
            command_argv=sys.argv,
            seed=args.seed,
            inputs=input_files,
            config_dict={},
            args={"triples": str(triples_path), "index_dir": str(index_dir)},
            warnings=["load_triples failed"],
            old_dir=None,
            data_file=triples_path,
            extra_fields={"phase": "post_run", "runner_name": TASK_NAME},
        )
        logger.close()
        return 1, exp_id

    # Check 2-4: load indexes
    for idx_name in ["forward", "backward", "hp_to_t"]:
        idx = _load_index(index_dir, idx_name)
        ok = idx is not None and len(idx) > 0
        per_sample.append({
            "qid": f"load_{idx_name}",
            "status": "ok" if ok else "fail",
            "question": f"Load {idx_name} index",
            "em": 1 if ok else 0,
            "f1": 1 if ok else 0,
            "error_type": "" if ok else "index_missing",
        })
        if not ok:
            failures.append({"qid": f"load_{idx_name}", "error_type": "index_missing"})

    # Check 5: sample lookups
    rng = random.Random(args.seed)
    if triples:
        sample = rng.sample(triples, min(5, len(triples)))
        forward = _load_index(index_dir, "forward")
        for i, t in enumerate(sample):
            h, p, o = t["subject"], t["predicate"], t["object"]
            if forward and h in forward:
                pts = forward[h]
                found = any(pt[0] == p and pt[1] == o for pt in pts)
            else:
                found = False
            ok = found
            per_sample.append({
                "qid": f"lookup_{i}",
                "status": "ok" if ok else "fail",
                "question": f"Lookup ({h[:30]}..., {p[:20]}...)",
                "error_type": "" if ok else "lookup_miss",
            })
            if not ok:
                failures.append({"qid": f"lookup_{i}", "error_type": "lookup_miss"})

    # Audit sample + case_studies (paper "图谱构建与质量分析" support)
    audit_n = min(max(1, args.audit_n), len(triples))
    indices = list(range(len(triples)))
    rng.shuffle(indices)
    audit_indices = indices[:audit_n]
    audit_rows: list[dict] = []
    for idx in audit_indices:
        t = triples[idx]
        audit_rows.append({
            "triple_id": idx + 1,
            "subject": t["subject"],
            "predicate": t["predicate"],
            "object": t["object"],
        })

    end_time = datetime.now().isoformat()
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    save_jsonl(per_sample, artifacts_dir / "per_sample_results.jsonl")

    # kg_sample_audit.csv
    audit_csv_path = artifacts_dir / "kg_sample_audit.csv"
    with open(audit_csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["triple_id", "subject", "predicate", "object", "audit_strict", "audit_relaxed", "remarks"])
        for r in audit_rows:
            w.writerow([r["triple_id"], r["subject"], r["predicate"], r["object"], "", "", ""])
    logger.log(f"Wrote kg_sample_audit.csv with {len(audit_rows)} rows")
    save_json(
        {"n": len(audit_rows), "seed": args.seed, "input": str(triples_path), "audit_strict": None, "audit_relaxed": None},
        artifacts_dir / "kg_sample_audit_summary.json",
    )

    # case_studies.md
    case_n = min(CASE_STUDIES_N, len(audit_rows))
    case_lines = ["# KG 样例展示 (case_studies)", "", f"从审计抽样中取前 {case_n} 条，用于快速检查数据格式。", ""]
    case_lines.append("| triple_id | subject | predicate | object |")
    case_lines.append("|-----------|---------|-----------|--------|")
    for r in audit_rows[:case_n]:
        subj = (r["subject"] or "")[:40].replace("|", "\\|")
        pred = (r["predicate"] or "")[:30].replace("|", "\\|")
        obj = (r["object"] or "")[:60].replace("|", "\\|")
        case_lines.append(f"| {r['triple_id']} | {subj} | {pred} | {obj} |")
    (artifacts_dir / "case_studies.md").write_text("\n".join(case_lines), encoding="utf-8")
    logger.log(f"Wrote case_studies.md with {case_n} samples")
    with open(artifacts_dir / "failures.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["qid", "question", "status", "is_executable", "http_status", "error_type", "em", "f1", "trace_path"])
        for r in failures:
            w.writerow([
                r.get("qid", ""),
                "",
                "fail",
                "",
                "",
                r.get("error_type", ""),
                "",
                "",
                "",
            ])

    write_repro_manifest(
        run_dir,
        run_id=exp_id,
        start_time=start_time,
        end_time=end_time,
        command_argv=sys.argv,
        seed=args.seed,
        inputs=input_files,
        config_dict={},
        args={"triples": str(triples_path), "index_dir": str(index_dir), "n_triples": len(triples)},
        warnings=[],
        old_dir=None,
        data_file=triples_path,
        extra_fields={"phase": "post_run", "runner_name": TASK_NAME, "n_checks": len(per_sample), "n_failures": len(failures)},
    )
    logger.log("KG smoke completed")
    logger.close()
    return 0, exp_id


if __name__ == "__main__":
    exit_code = 0
    run_id_for_report = None
    try:
        exit_code, run_id_for_report = main()
    except Exception as e:
        print(e, file=sys.stderr)
        exit_code = 1
        run_id_for_report = None
    finally:
        if run_id_for_report:
            run_dir = ROOT / "runs" / run_id_for_report
            run_log_path = run_dir / "run.log"

            def _validate(run_dir: Path) -> tuple[bool, list[str]]:
                errs = []
                for p in [run_dir / "artifacts" / "per_sample_results.jsonl", run_dir / "artifacts" / "failures.csv", run_dir / "repro_manifest.json"]:
                    if not p.exists():
                        errs.append(f"{p.name} missing")
                return (len(errs) == 0, errs)

            ok, errs = _validate(run_dir)
            with open(run_log_path, "a", encoding="utf-8") as f:
                f.write("validate_audit_artifacts: PASS\n" if ok else f"validate_audit_artifacts: FAIL ({'; '.join(errs)})\n")
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("gen_run_report", ROOT / "scripts" / "gen_run_report.py")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                out_path = mod.generate_report(run_id_for_report, TASK_NAME)
                with open(run_log_path, "a", encoding="utf-8") as f:
                    f.write(f"Report saved to {out_path}\n")
                print(f"Report: {out_path}")
            except Exception as e:
                print(f"gen_run_report: {e}", file=sys.stderr)
    sys.exit(exit_code)
