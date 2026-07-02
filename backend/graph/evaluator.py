import re
import time
from langchain_core.prompts import PromptTemplate
from backend.graph.state import CustomerRiskState
from backend.utils.llm import get_llm
from backend.prompts.templates import AUDITOR_PROMPT, REPAIR_PROMPT

# NOVELTY (Convergence Telemetry): matches the "SCORE: <float>" line the
# auditor prompt now emits, so every evaluator pass yields a continuous
# compliance score rather than only a binary APPROVED/REJECTED verdict.
_SCORE_PATTERN = re.compile(r"SCORE:\s*([0-9]*\.?[0-9]+)", re.IGNORECASE)


def _extract_score(content: str, approved: bool) -> float:
    """
    Pull the auditor's numeric compliance score out of its response.
    Falls back to a binary proxy (1.0 / 0.0) if the model omits the SCORE
    line under prompt drift, so telemetry is never silently dropped.
    """
    match = _SCORE_PATTERN.search(content)
    if match:
        try:
            return max(0.0, min(1.0, float(match.group(1))))
        except ValueError:
            pass
    return 1.0 if approved else 0.0


def auditor_evaluator(state: CustomerRiskState) -> dict:
    """
    Layer 5: Evaluation Agent (Auditor)
    Checks if drafted monthly payments exceed 40% of net balance.

    NOVELTY: also appends a telemetry entry per call — {iteration, score,
    status, latency_s} — to state["repair_history"], giving the full
    convergence trajectory of the bounded repair loop for Sections 3.1 and
    3.14.1 of the paper. This is additive instrumentation only; it does not
    change the pass/fail routing behavior of the loop.
    """
    llm = get_llm(temperature=0.1)
    prompt = PromptTemplate.from_template(AUDITOR_PROMPT)
    chain = prompt | llm

    start = time.monotonic()
    response = chain.invoke(state)
    elapsed = time.monotonic() - start
    content = response.content

    approved = "STATUS: REJECTED" not in content.upper()
    issues = [] if approved else ["Auditor rejected draft due to 40% EMI rule."]
    score = _extract_score(content, approved)

    repair_count = state.get("repair_count", 0)
    telemetry_entry = {
        "iteration": repair_count,
        "score": score,
        "status": "APPROVED" if approved else "REJECTED",
        "latency_s": round(elapsed, 4),
    }

    return {
        "eval_issues": issues,
        "final_offer": content if approved else state.get("drafted_offer", ""),
        "repair_history": [telemetry_entry],
    }


def repair_agent(state: CustomerRiskState) -> dict:
    """
    Layer 5 (Repair): Auto-Repair Loop
    Re-drafts the offer to pass compliance.
    """
    llm = get_llm(temperature=0.1)
    prompt = PromptTemplate.from_template(REPAIR_PROMPT)
    chain = prompt | llm

    response = chain.invoke(state)

    repair_count = state.get("repair_count", 0) + 1

    return {
        "drafted_offer": response.content,
        "repair_count": repair_count
    }


def eval_router(state: CustomerRiskState) -> str:
    """Routes back to repair if issues exist, else to guardrail"""
    issues = state.get("eval_issues", [])
    repair_count = state.get("repair_count", 0)

    # Limit to 2 repairs to prevent infinite loops
    if issues and repair_count < 2:
        return "repair_agent"
    return "security_guardrail"
