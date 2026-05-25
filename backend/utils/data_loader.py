import os
import random
import pandas as pd
import kagglehub
from faker import Faker

fake = Faker()

def load_and_enhance_dataset():
    """
    Generates 10 instant mock applicants for UI testing without downloading massive datasets.
    """
    print("Generating instant mock dataset for UI testing...")
    custom_records = []
    
    industries = ["Tech", "Healthcare", "Retail", "Finance", "Construction", "Gig Economy"]
    risk_types = ["None", "High_Debt_Exposure", "Identity_Theft_Risk", "Active_Default", "Subprime_Profile"]
    loan_types = ["Auto Loan, Credit-Builder", "Payday Loan, Personal Loan", "Mortgage, Student Loan", "Not Specified"]
    
    for i in range(10):
        income = random.randint(30000, 150000)
        debt = random.randint(5000, 80000)
        
        custom_records.append({
            "Customer_ID": f"CUST-{random.randint(10000, 99999)}",
            "Name": fake.name(),
            "Annual_Income": income,
            "Monthly_Inhand_Salary": income / 12,
            "Outstanding_Debt": debt,
            "Credit_Score": random.choice(["Good", "Standard", "Poor"]),
            "Highest_Risk_Type": random.choice(risk_types),
            "Type_of_Loan": random.choice(loan_types),
            "Num_of_Delayed_Payment": random.randint(0, 15),
            "Credit_Utilization_Ratio": random.uniform(0.1, 0.95),
            "Amount_invested_monthly": random.randint(0, 2000),
            "Monthly_Balance": random.randint(200, 5000),
            "Total_EMI_per_month": random.randint(100, 3000),
            "Num_Credit_Inquiries": random.randint(0, 10),
            "Payment_Behaviour": random.choice(["Low_spent_Small_value_payments", "High_spent_Large_value_payments"])
        })
        
    return custom_records
