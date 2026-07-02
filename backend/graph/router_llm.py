"""
Layer 2 (Baseline Variant) — LLM-Delegated Risk Classification Router.

This module exists ONLY to construct the empirical baseline referenced in
Sections 3.5 and 3.14.4 of the paper: what happens if the routing decision
normally made by pure deterministic Python code (backend/graph/router.py)
is instead delegated to an LLM prompt over the same input fields?

It is NOT part of the production pipeline by default and should only be
wired in via ROUTER_MODE=llm (see backend/graph/pipeline.py), strictly for
benchmarking against the deterministic router.
"""
import time
from langchain_core.prompts import PromptTemplate
from backend.graph.state import CustomerRiskState
from backend.utils.llm import get_llm
from backend.utils.json_parser import parse_json_safe
from backend.prompts.templates import ROUTER_LLM_PROMPT

_VALID_TRACKS = {
    "prime_rewards_optimization_track",
    "subprime_secured_card_track",
    "dispute_audit_track",
}

_DEFAULT_TRACK = "subprime_secured_card_track"  # conservative fallback on parse failure


def risk_classification_router_llm(state: CustomerRiskState) -> dict:
    """
    Baseline Layer 2: routes the applicant using an LLM prompt instead of
    the deterministic DTI/credit_score rule. Records wall-clock latency on
    the state so it can be directly compared against the deterministic
    router's near-zero routing cost (Section 3.6 / 3.14.4).
    """
    llm = get_llm(temperature=0.0)
    prompt = PromptTemplate.from_template(ROUTER_LLM_PROMPT)
    chain = prompt | llm

    debt = float(state.get("outstanding_debt", 0) or 0)
    income = float(state.get("annual_income", 1) or 1)
    dti = debt / max(income, 1.0)

    start = time.monotonic()
    response = chain.invoke({
        "credit_score": state.get("credit_score"),
        "outstanding_debt": debt,
        "annual_income": income,
        "debt_to_income_ratio": round(dti, 4),
        "highest_risk_type": state.get("Highest_Risk_Type"),
    })
    elapsed = time.monotonic() - start

    parsed = parse_json_safe(response.content, default={"risk_track": _DEFAULT_TRACK})
    track = parsed.get("risk_track", _DEFAULT_TRACK)
    if track not in _VALID_TRACKS:
        track = _DEFAULT_TRACK

    return {
        "risk_track": track,
        "router_latency_s": round(elapsed, 4),
        "router_mode_used": "llm",
    }
