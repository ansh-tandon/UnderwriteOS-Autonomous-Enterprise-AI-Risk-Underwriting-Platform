from langchain_core.prompts import PromptTemplate
from backend.graph.state import CustomerRiskState
from backend.utils.llm import get_llm
from backend.prompts.templates import AUDITOR_PROMPT, REPAIR_PROMPT

def auditor_evaluator(state: CustomerRiskState) -> dict:
    """
    Layer 5: Evaluation Agent (Auditor)
    Checks if drafted monthly payments exceed 40% of net balance.
    """
    llm = get_llm(temperature=0.1)
    prompt = PromptTemplate.from_template(AUDITOR_PROMPT)
    chain = prompt | llm
    
    response = chain.invoke(state)
    content = response.content
    
    issues = []
    if "STATUS: REJECTED" in content.upper():
        issues.append("Auditor rejected draft due to 40% EMI rule.")
        
    return {
        "eval_issues": issues,
        "final_offer": content if not issues else state.get("drafted_offer", "")
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
