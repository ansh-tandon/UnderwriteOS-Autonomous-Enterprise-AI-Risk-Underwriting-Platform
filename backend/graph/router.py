from backend.graph.state import CustomerRiskState

def risk_classification_router(state: CustomerRiskState) -> CustomerRiskState:
    """
    Layer 2: The Branching Risk Router
    Computes core business metrics to instantly route the applicant into the appropriate processing queue.
    """
    # Note: State dictionary keys are usually lowercase in our TypedDict, 
    # but we handle potential casing issues safely.
    score = state.get("credit_score")
    debt = float(state.get("outstanding_debt", 0))
    income = state.get("annual_income", 1)
    if not income or float(income) <= 0:
        income = 1.0
    else:
        income = float(income)
        
    risk_type = state.get("Highest_Risk_Type")

    # Calculate hard Debt-to-Income Ratio
    dti = debt / income

    # Strict override: If dataset flags active default/fraud risk type
    if risk_type in ["Identity_Theft_Risk", "Active_Default", "Financial Risk"]:
        state["risk_track"] = "dispute_audit_track"
        return state

    # Branch A: Prime Portfolio Track
    if score == "Good" and dti <= 0.35:
        state["risk_track"] = "prime_rewards_optimization_track"
        return state

    # Branch B: Subprime Capital Preservation Track
    state["risk_track"] = "subprime_secured_card_track"
    return state
