import os
from langgraph.graph import StateGraph, END
from backend.graph.state import CustomerRiskState
from backend.graph.ingestion import ingestion_masking
from backend.graph.router import risk_classification_router
from backend.graph.router_llm import risk_classification_router_llm
from backend.graph.branches import branch_prime, branch_subprime, branch_dispute
from backend.graph.rag_engine import self_healing_rag
from backend.graph.evaluator import auditor_evaluator, repair_agent, eval_router
from backend.graph.guardrail import security_guardrail


def build_pipeline(router_mode: str = None):
    """
    NOVELTY (Baseline Comparison, Sections 3.5 / 3.14.4): router_mode selects
    between the production deterministic router and the LLM-delegated
    baseline router, so both variants can be run over the same dataset with
    everything else in the graph held fixed.

    router_mode: "deterministic" (default, production) or "llm" (baseline
    used only for comparison experiments). Falls back to the ROUTER_MODE
    env var, then to "deterministic" if unset.
    """
    router_mode = router_mode or os.getenv("ROUTER_MODE", "deterministic")
    router_node = (
        risk_classification_router if router_mode == "deterministic"
        else risk_classification_router_llm
    )

    builder = StateGraph(CustomerRiskState)

    # Layer 1
    builder.add_node("ingestion_masking", ingestion_masking)

    # Layer 2 (swappable: deterministic vs. LLM baseline)
    builder.add_node("risk_classification_router", router_node)

    # Layer 3
    builder.add_node("branch_prime", branch_prime)
    builder.add_node("branch_subprime", branch_subprime)
    builder.add_node("branch_dispute", branch_dispute)

    # Layer 4
    builder.add_node("self_healing_rag", self_healing_rag)

    # Layer 5
    builder.add_node("auditor_evaluator", auditor_evaluator)
    builder.add_node("repair_agent", repair_agent)

    # Layer 6
    builder.add_node("security_guardrail", security_guardrail)

    # Edges
    builder.set_entry_point("ingestion_masking")
    builder.add_edge("ingestion_masking", "risk_classification_router")

    # Conditional Branching from Router
    def route_to_branch(state: CustomerRiskState):
        track = state.get("risk_track")
        if track == "prime_rewards_optimization_track":
            return "branch_prime"
        elif track == "subprime_secured_card_track":
            return "branch_subprime"
        return "branch_dispute"

    builder.add_conditional_edges(
        "risk_classification_router",
        route_to_branch,
        {
            "branch_prime": "branch_prime",
            "branch_subprime": "branch_subprime",
            "branch_dispute": "branch_dispute"
        }
    )

    # Converge at Layer 4
    builder.add_edge("branch_prime", "self_healing_rag")
    builder.add_edge("branch_subprime", "self_healing_rag")
    builder.add_edge("branch_dispute", "self_healing_rag")

    # Layer 4 to 5
    builder.add_edge("self_healing_rag", "auditor_evaluator")

    # Loop at Layer 5
    builder.add_conditional_edges(
        "auditor_evaluator",
        eval_router,
        {
            "repair_agent": "repair_agent",
            "security_guardrail": "security_guardrail"
        }
    )
    builder.add_edge("repair_agent", "auditor_evaluator")

    # End
    builder.add_edge("security_guardrail", END)

    return builder.compile()

# Expose compiled graph (production default: deterministic router)
graph = build_pipeline()
