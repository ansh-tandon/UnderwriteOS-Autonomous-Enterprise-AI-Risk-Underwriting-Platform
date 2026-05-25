from backend.graph.state import CustomerRiskState
import re

def ingestion_masking(state: CustomerRiskState) -> CustomerRiskState:
    """
    Layer 1: Ingestion & Compliance Masking
    Standardizes formats and isolates ECOA restricted fields.
    """
    # 1. Masking Fields to avoid demographic bias and identity exposure
    state["age"] = None
    state["occupation"] = "[REDACTED]"
    state["ssn"] = "[REDACTED]"
    
    # 2. Standardization
    # Convert Credit_History_Age (e.g. "22 Years and 3 Months") to integer months
    history_str = str(state.get("credit_history_age", ""))
    total_months = 0
    if history_str and history_str != "NA":
        # Extract years
        years_match = re.search(r'(\d+)\s*Years?', history_str, re.IGNORECASE)
        months_match = re.search(r'(\d+)\s*Months?', history_str, re.IGNORECASE)
        
        years = int(years_match.group(1)) if years_match else 0
        months = int(months_match.group(1)) if months_match else 0
        
        total_months = (years * 12) + months
        
    state["credit_history_age_months"] = total_months
    
    return state
