"""
Experiment harness: deterministic router vs. LLM-baseline router.

Populates the comparison data for Sections 3.5 and 3.14.4 of the paper.
Runs the same applicant set through both router variants — everything else
held fixed — and logs per-applicant track agreement and per-router latency.

This intentionally does NOT run the full 6-layer pipeline (branch/evaluator/
repair calls are skipped); it isolates the routing decision itself and its
latency, since that is the specific comparison the paper makes.

Usage (run from repo root):
    python experiments/run_router_comparison.py --n 100 --out results/router_comparison.csv

Requires a live LLM API key configured per backend/utils/llm.py, since the
LLM baseline router makes real calls.
"""
import argparse
import csv
import glob
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from backend.graph.router import risk_classification_router
from backend.graph.router_llm import risk_classification_router_llm


def _row_to_state(row: dict) -> dict:
    return {
        "credit_score": row.get("Credit_Score"),
        "outstanding_debt": row.get("Outstanding_Debt", 0),
        "annual_income": row.get("Annual_Income", 1),
        "Highest_Risk_Type": row.get("Highest_Risk_Type"),
    }


def load_applicants(n: int) -> list:
    frames = []
    for path in glob.glob(os.path.join("datasets", "*.csv")):
        frames.append(pd.read_csv(path))
    if not frames:
        raise FileNotFoundError(
            "No CSVs found under datasets/. Run this script from the repo root."
        )
    df = pd.concat(frames, ignore_index=True)
    if n < len(df):
        df = df.sample(n=n, random_state=42)
    return df.to_dict(orient="records")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--out", type=str, default="results/router_comparison.csv")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    applicants = load_applicants(args.n)
    rows = []

    for i, applicant in enumerate(applicants):
        state = _row_to_state(applicant)

        t0 = time.monotonic()
        det_state = risk_classification_router(dict(state))
        det_latency = time.monotonic() - t0
        det_track = det_state.get("risk_track")

        t0 = time.monotonic()
        llm_result = risk_classification_router_llm(dict(state))
        llm_latency = time.monotonic() - t0
        llm_track = llm_result.get("risk_track")

        rows.append({
            "index": i,
            "customer_id": applicant.get("Customer_ID", i),
            "deterministic_track": det_track,
            "llm_track": llm_track,
            "agree": det_track == llm_track,
            "deterministic_latency_s": round(det_latency, 5),
            "llm_latency_s": round(llm_latency, 5),
        })
        print(f"[{i + 1}/{len(applicants)}] det={det_track} llm={llm_track} "
              f"agree={det_track == llm_track}")

    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    agreement_rate = sum(r["agree"] for r in rows) / len(rows)
    avg_det_latency = sum(r["deterministic_latency_s"] for r in rows) / len(rows)
    avg_llm_latency = sum(r["llm_latency_s"] for r in rows) / len(rows)

    print("\n--- Summary ---")
    print(f"Agreement rate:            {agreement_rate:.2%}")
    print(f"Avg deterministic latency: {avg_det_latency:.5f}s")
    print(f"Avg LLM router latency:    {avg_llm_latency:.5f}s")
    print(f"Speedup factor:            {avg_llm_latency / max(avg_det_latency, 1e-9):.1f}x")
    print(f"Results written to:        {args.out}")


if __name__ == "__main__":
    main()
