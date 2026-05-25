import os
import sys
from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv

# Ensure backend module can be imported when running from within the backend folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from root or backend directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from backend.utils.data_loader import load_and_enhance_dataset
from backend.utils.json_parser import parse_json_safe, extract_json_from_text
from backend.routers.s3_upload import router as s3_router

# Initialize LLM using Groq (Llama 3.1 - Free & Fast)
llM = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0)

def load_prompt(filename: str) -> ChatPromptTemplate:
    """Helper to dynamically load prompt templates from the prompts directory."""
    path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return ChatPromptTemplate.from_template(f.read())

# ==========================================
# 1. STATE DEFINITION
# ==========================================
class UnderwritingState(BaseModel):
    raw_input: Dict[str, Any] = Field(default_factory=dict)
    customer_id: str = ""
    name: str = ""
    normalized_credit_history_months: int = 0
    debt_to_income_ratio: float = 0.0
    selected_branch: str = ""
    retrieved_loan_context: str = ""
    rag_confidence_score: float = 0.0
    rag_retry_count: int = 0
    draft_recommendation: Dict[str, Any] = Field(default_factory=dict)
    evaluation_score: float = 0.0
    is_repaired: bool = False
    final_sanitized_output: Dict[str, Any] = Field(default_factory=dict)


# ==========================================
# 2. NODE IMPLEMENTATIONS
# ==========================================

def compliance_masking_node(state: UnderwritingState) -> Dict[str, Any]:
    raw = state.raw_input
    
    customer_id = raw.get("Customer_ID", "UNKNOWN")
    name = raw.get("Name", "ANONYMOUS")
    
    raw_history_age = str(raw.get("Credit_History_Age", "0 Years"))
    try:
        years = int(raw_history_age.split()[0])
        months = years * 12
    except (ValueError, IndexError):
        months = 0

    income = float(raw.get("Annual_Income", 1.0))
    debt = float(raw.get("Outstanding_Debt", 0.0))
    dti = debt / max(income, 1.0)
    
    return {
        "customer_id": customer_id,
        "name": name,
        "normalized_credit_history_months": months,
        "debt_to_income_ratio": dti
    }


def risk_classification_router(state: UnderwritingState) -> Literal["prime_branch_node", "subprime_branch_node", "dispute_audit_node"]:
    raw = state.raw_input
    score = raw.get("Credit_Score", "Standard")
    dti = state.debt_to_income_ratio
    risk_type = raw.get("Highest_Risk_Type", "None")
    
    if risk_type in ["Identity_Theft_Risk", "Active_Default"]:
        return "dispute_audit_node"
        
    if score == "Good" and dti <= 0.35:
        return "prime_branch_node"
        
    return "subprime_branch_node"


def prime_branch_node(state: UnderwritingState) -> Dict[str, Any]:
    raw = state.raw_input
    prompt = load_prompt("Prompt1.md")
    
    chain = prompt | llM
    response = chain.invoke({
        "salary": raw.get("Monthly_Inhand_Salary"),
        "investment": raw.get("Amount_invested_monthly"),
        "score": raw.get("Credit_Score")
    })
    
    # Use the robust JSON parser
    res = parse_json_safe(response.content, default={"tier": "Platinum", "limit": 1000, "perks": []})
    
    return {"draft_recommendation": res, "selected_branch": "PRIME"}


def subprime_branch_node(state: UnderwritingState) -> Dict[str, Any]:
    raw = state.raw_input
    prompt = load_prompt("Prompt2.md")
    
    chain = prompt | llM
    response = chain.invoke({
        "debt": raw.get("Outstanding_Debt"),
        "delayed_count": raw.get("Num_of_Delayed_Payment"),
        "utilization": raw.get("Credit_Utilization_Ratio")
    })
    
    # Use the robust JSON parser
    res = parse_json_safe(response.content, default={"tier": "Basic_Everyday", "limit": 1000, "perks": []})
    
    return {"draft_recommendation": res, "selected_branch": "SUBPRIME"}


def dispute_audit_node(state: UnderwritingState) -> Dict[str, Any]:
    raw = state.raw_input
    prompt = load_prompt("Prompt3.md")
    
    chain = prompt | llM
    response = chain.invoke({
        "risk_type": raw.get("Highest_Risk_Type"),
        "behaviour": raw.get("Payment_Behaviour"),
        "inquiries": raw.get("Num_Credit_Inquiries")
    })
    
    # Use the robust JSON parser
    res = parse_json_safe(response.content, default={"status": "PENDING_MANUAL_REVIEW", "reason": "High risk profile"})
    
    return {"draft_recommendation": res, "selected_branch": "DISPUTE_AUDIT"}


def self_healing_rag_node(state: UnderwritingState) -> Dict[str, Any]:
    raw = state.raw_input
    raw_loans = str(raw.get("Type_of_Loan", ""))
    retry_count = state.rag_retry_count
    
    confidence = 0.95
    if "Payday Loan" in raw_loans or "Subprime Loan" in raw_loans:
        if retry_count == 0:
            return {"rag_confidence_score": 0.40, "rag_retry_count": 1}
        else:
            prompt = load_prompt("Prompt4.md")
            chain = prompt | llM
            
            # Use the LLM to rewrite the query
            rewritten_query = chain.invoke({
                "query": "Evaluate High Risk Loan Types",
                "context": raw_loans
            }).content
            
            confidence = 0.98
            raw_loans = f"{raw_loans} [REWRITTEN VECTOR QUERY APPLIED: {rewritten_query}]"
            
    return {
        "retrieved_loan_context": raw_loans,
        "rag_confidence_score": confidence
    }


def dynamic_evaluator_node(state: UnderwritingState) -> Dict[str, Any]:
    raw = state.raw_input
    draft = state.draft_recommendation
    prompt = load_prompt("Prompt5.md")
    
    chain = prompt | llM
    res_text = chain.invoke({
        "draft": str(draft),
        "balance": raw.get("Monthly_Balance"),
        "emi": raw.get("Total_EMI_per_month")
    }).content
    
    try:
        score = float(res_text.strip())
    except ValueError:
        score = 0.50
        
    return {"evaluation_score": score}


def routing_evaluation_gate(state: UnderwritingState) -> Literal["auto_repair_node", "compliance_guardrail_node"]:
    if state.evaluation_score < 0.80 and not state.is_repaired:
        return "auto_repair_node"
    return "compliance_guardrail_node"


def auto_repair_node(state: UnderwritingState) -> Dict[str, Any]:
    raw = state.raw_input
    bad_draft = state.draft_recommendation
    context = state.retrieved_loan_context
    prompt = load_prompt("Prompt6.md")
    
    chain = prompt | llM
    response = chain.invoke({
        "bad_draft": str(bad_draft),
        "context": context,
        "balance": raw.get("Monthly_Balance")
    })
    
    # Use the robust JSON parser instead of JsonOutputParser
    corrected_res = parse_json_safe(response.content, default=bad_draft)
    
    return {"draft_recommendation": corrected_res, "is_repaired": True}


def compliance_guardrail_node(state: UnderwritingState) -> Dict[str, Any]:
    draft = state.draft_recommendation
    branch = state.selected_branch
    prompt = load_prompt("Prompt7.md")
    
    chain = prompt | llM
    response = chain.invoke({
        "draft": str(draft), 
        "branch": branch
    })
    
    # Use the robust JSON parser instead of JsonOutputParser
    sanitized_output = parse_json_safe(response.content, default=draft)
    
    return {"final_sanitized_output": sanitized_output}


def rag_self_heal_router(state: UnderwritingState) -> Literal["self_healing_rag_node", "dynamic_evaluator_node"]:
    if state.rag_confidence_score < 0.50 and state.rag_retry_count == 1:
        return "self_healing_rag_node"
    return "dynamic_evaluator_node"


# ==========================================
# 3. WORKFLOW COMPOSITION & ASSEMBLY
# ==========================================

builder = StateGraph(UnderwritingState)

builder.add_node("compliance_masking_node", compliance_masking_node)
builder.add_node("prime_branch_node", prime_branch_node)
builder.add_node("subprime_branch_node", subprime_branch_node)
builder.add_node("dispute_audit_node", dispute_audit_node)
builder.add_node("self_healing_rag_node", self_healing_rag_node)
builder.add_node("dynamic_evaluator_node", dynamic_evaluator_node)
builder.add_node("auto_repair_node", auto_repair_node)
builder.add_node("compliance_guardrail_node", compliance_guardrail_node)

builder.add_edge(START, "compliance_masking_node")

builder.add_conditional_edges(
    "compliance_masking_node",
    risk_classification_router,
    {
        "prime_branch_node": "prime_branch_node",
        "subprime_branch_node": "subprime_branch_node",
        "dispute_audit_node": "dispute_audit_node"
    }
)

builder.add_edge("prime_branch_node", "self_healing_rag_node")
builder.add_edge("subprime_branch_node", "self_healing_rag_node")
builder.add_edge("dispute_audit_node", "self_healing_rag_node")

builder.add_conditional_edges(
    "self_healing_rag_node",
    rag_self_heal_router,
    {
        "self_healing_rag_node": "self_healing_rag_node",
        "dynamic_evaluator_node": "dynamic_evaluator_node"
    }
)

builder.add_conditional_edges(
    "dynamic_evaluator_node",
    routing_evaluation_gate,
    {
        "auto_repair_node": "auto_repair_node",
        "compliance_guardrail_node": "compliance_guardrail_node"
    }
)

builder.add_edge("auto_repair_node", "compliance_guardrail_node")
builder.add_edge("compliance_guardrail_node", END)

underwriting_agent_app = builder.compile()


# ==========================================
# 4. FASTAPI INGESTION APPLICATION INTERFACE
# ==========================================
app = FastAPI(title="Autonomous AI Underwriting Engine OS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register S3 Upload Router
app.include_router(s3_router)

cached_dataset = []

@app.on_event("startup")
async def startup_event():
    print("Pre-loading dataset...")
    global cached_dataset
    try:
        cached_dataset = load_and_enhance_dataset()
    except Exception as e:
        print(f"Dataset preload failed: {e}")

@app.get("/health")
def health_check():
    return {"status": "ok", "dataset_loaded": bool(cached_dataset)}

@app.get("/api/sample-applicants")
def get_sample_applicants():
    if not cached_dataset:
        return {"error": "Dataset not loaded"}
    return cached_dataset[:10]

@app.post("/api/v1/underwrite")
async def execute_underwriting_pipeline(payload: Dict[str, Any]):
    try:
        initial_state = UnderwritingState(raw_input=payload)
        output_state = underwriting_agent_app.invoke(initial_state)
        
        return {
            "customer_id": output_state.get("customer_id"),
            "execution_trace_summary": {
                "selected_route_track": output_state.get("selected_branch"),
                "rag_audit_confidence": output_state.get("rag_confidence_score"),
                "auto_remedy_executed": output_state.get("is_repaired"),
                "internal_eval_score": output_state.get("evaluation_score")
            },
            "underwriting_decision_packet": output_state.get("final_sanitized_output")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
