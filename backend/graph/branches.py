from langchain_core.prompts import PromptTemplate
from backend.graph.state import CustomerRiskState
from backend.utils.llm import get_llm
from backend.prompts.templates import (
    PRIME_AGENT_PROMPT,
    SUBPRIME_AGENT_PROMPT,
    DISPUTE_AGENT_PROMPT
)

def branch_prime(state: CustomerRiskState) -> dict:
    """Layer 3: Prime Rewards Optimization Agent"""
    llm = get_llm(temperature=0.1)
    prompt = PromptTemplate.from_template(PRIME_AGENT_PROMPT)
    chain = prompt | llm
    
    response = chain.invoke(state)
    return {"drafted_offer": response.content}

def branch_subprime(state: CustomerRiskState) -> dict:
    """Layer 3: Subprime Credit Builder Agent"""
    llm = get_llm(temperature=0.1)
    prompt = PromptTemplate.from_template(SUBPRIME_AGENT_PROMPT)
    chain = prompt | llm
    
    response = chain.invoke(state)
    return {"drafted_offer": response.content}

def branch_dispute(state: CustomerRiskState) -> dict:
    """Layer 3: Dispute / Audit Agent"""
    llm = get_llm(temperature=0.1)
    prompt = PromptTemplate.from_template(DISPUTE_AGENT_PROMPT)
    chain = prompt | llm
    
    response = chain.invoke(state)
    return {"drafted_offer": response.content}
