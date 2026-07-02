"""
Experiment harness: repair-loop convergence telemetry.

Populates the data for Sections 3.1 (convergence stability) and 3.14.1
(error distribution at routing boundaries) of the paper.

Runs applicants through the full pipeline (backend/graph/pipeline.py,
router_mode="deterministic") and aggregates the per-iteration
state["repair_history"] trajectory that backend/graph/evaluator.py now
records on every auditor pass.

Usage (run from repo root):
    python experiments/run_repair_telemetry.py --n 100 --out results/repair_telemetry.csv

Requires a live LLM API key configured per backend/utils/llm.py.
"""
import argparse
import csv
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from backend.graph.pipeline import build_pipeline
from backend.graph.state import CustomerRiskState


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


def _row_to_state(row: dict) -> dict:
    """Minimal field mapping; extend as needed to match your CSV schema."""
    debt = float(row.get("Outstanding_Debt", 0) or 0)
    income = float(row.get("Annual_Income", 1) or 1)
    return {
        "customer_id": row.get("Customer_ID", ""),
        "name": row.get("Name", ""),
        "annual_income": income,
        "monthly_inhand_salary": row.get("Monthly_Inhand_Salary", income / 12),
        "outstanding_debt": debt,
        "credit_utilization_ratio": row.get("Credit_Utilization_Ratio", 0),
        "total_emi_per_month": row.get("Total_EMI_per_month", 0),
        "monthly_balance": row.get("Monthly_Balance", 0),
        "amount_invested_monthly": row.get("Amount_invested_monthly", 0),
        "credit_score": row.get("Credit_Score", "Standard"),
        "credit_mix": row.get("Credit_Mix", ""),
        "changed_credit_limit": row.get("Changed_Credit_Limit", 0),
        "num_credit_inquiries": row.get("Num_Credit_Inquiries", 0),
        "num_of_delayed_payment": row.get("Num_of_Delayed_Payment", 0),
        "delay_from_due_date": row.get("Delay_from_due_date", 0),
        "type_of_loan": row.get("Type_of_Loan", ""),
        "Highest_Risk_Type": row.get("Highest_Risk_Type", "None"),
        "payment_behaviour": row.get("Payment_Behaviour", ""),
        "repair_count": 0,
        "repair_history": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--out", type=str, default="results/repair_telemetry.csv")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    graph = build_pipeline(router_mode="deterministic")
    applicants = load_applicants(args.n)

    rows = []
    for i, applicant in enumerate(applicants):
        initial_state: CustomerRiskState = _row_to_state(applicant)
        try:
            final_state = graph.invoke(initial_state)
        except Exception as e:
            print(f"[{i + 1}/{len(applicants)}] ERROR: {e}")
            continue

        history = final_state.get("repair_history", [])
        for entry in history:
            rows.append({
                "customer_id": applicant.get("Customer_ID", i),
                "risk_track": final_state.get("risk_track"),
                "iteration": entry["iteration"],
                "score": entry["score"],
                "status": entry["status"],
                "latency_s": entry["latency_s"],
                "final_compliance_status": final_state.get("compliance_status"),
                "total_repairs": final_state.get("repair_count", 0),
            })
        print(f"[{i + 1}/{len(applicants)}] track={final_state.get('risk_track')} "
              f"repairs={final_state.get('repair_count', 0)} "
              f"final={final_state.get('compliance_status')}")

    if not rows:
        print("No telemetry collected.")
        return

    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    convergence_rate = sum(
        1 for r in rows if r["iteration"] == r["total_repairs"] and r["status"] == "APPROVED"
    ) / max(len({r["customer_id"] for r in rows}), 1)

    print("\n--- Summary ---")
    print(f"Total telemetry rows:   {len(rows)}")
    print(f"Applicants processed:   {len({r['customer_id'] for r in rows})}")
    print(f"Approx. convergence rate: {convergence_rate:.2%}")
    print(f"Results written to:     {args.out}")


if __name__ == "__main__":
    main()
