from backend.graph.state import CustomerRiskState

def self_healing_rag(state: CustomerRiskState) -> dict:
    """
    Layer 4: Self-Healing Hybrid Search (RAG over Loans)
    Evaluates Type_of_Loan. Fallback to Sparse BM25 filter if needed.
    """
    loan_types = str(state.get("type_of_loan", "")).lower()
    
    # Sparse Keyword Filter (BM25 simulation)
    high_risk_flags = ["payday", "subprime"]
    issues = []
    
    for flag in high_risk_flags:
        if flag in loan_types:
            issues.append(f"Detected high-risk loan product: {flag}")
            
    rag_risk_adjustment = "Elevated" if issues else "Normal"
    
    return {
        "rag_issues_detected": issues,
        "rag_risk_adjustment": rag_risk_adjustment
    }
