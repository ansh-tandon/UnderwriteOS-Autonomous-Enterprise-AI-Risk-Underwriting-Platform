"""
LangGraph State Definition for Credit Risk Identification Pipeline.
All nodes read from and write to this shared state object.
"""
from __future__ import annotations
from typing import Annotated, Optional
import operator
from typing_extensions import TypedDict


class CustomerRiskState(TypedDict):
    # ── Raw Input Fields (from Excel row) ──────────────────────────────────
    customer_id: str
    name: str
    age: Optional[int]                # Masked
    ssn: Optional[str]                # Masked
    occupation: Optional[str]         # Masked
    employment_type: str              
    employment_duration_years: float
    industry_sector: str
    city: str
    state_region: str
    num_dependents: int

    # ── Financial Fields ────────────────────────────────────────────────────
    annual_income: float
    monthly_inhand_salary: float
    monthly_rent: float
    outstanding_debt: float
    credit_utilization_ratio: float   
    total_emi_per_month: float
    monthly_balance: float
    amount_invested_monthly: float
    portfolio_investment_value: float
    avg_monthly_spending: float

    # ── Credit Profile Fields ───────────────────────────────────────────────
    credit_score: str                 
    credit_history_age: str           # Original raw text
    credit_history_age_months: int    # Converted count
    credit_mix: str                  
    num_bank_accounts: int
    num_credit_card: int
    interest_rate: float             
    num_of_loan: int
    type_of_loan: str
    changed_credit_limit: float
    num_credit_inquiries: int
    payment_of_min_amount: str       
    payment_behaviour: str
    delay_from_due_date: int         
    num_of_delayed_payment: int

    # ── Custom / Derived Fields ─────────────────────────────────────────────
    Highest_Risk_Type: str           # From custom dataset

    # ── Computed / Router Fields ────────────────────────────────────────────
    risk_track: str                  # prime / subprime / dispute
    
    # ── Branch Outputs ──────────────────────────────────────────────────────
    drafted_offer: str
    branch_notes: str

    # ── RAG Engine Fields ───────────────────────────────────────────────────
    rag_issues_detected: list
    rag_risk_adjustment: str

    # ── Evaluation & Repair Loop ────────────────────────────────────────────
    eval_issues: list
    repair_count: int
    final_offer: str          

    # ── Compliance & Final Output ───────────────────────────────────────────
    compliance_status: str           
    sanitized_output: dict
    error: Optional[str]
