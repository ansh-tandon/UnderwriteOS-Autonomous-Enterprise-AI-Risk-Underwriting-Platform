import time
from backend.utils.db import Base, engine
from backend.utils.embeddings import init_vector_store

def setup_databases():
    print("--- Starting Database Setup ---")
    
    # 1. Postgres Setup
    print("\n1. Setting up PostgreSQL Tables...")
    try:
        # Create all tables defined in db.py (Applicant, RiskAssessment)
        Base.metadata.create_all(bind=engine)
        print("✅ Postgres tables created successfully.")
    except Exception as e:
        print(f"❌ Failed to connect to Postgres. Make sure the container is running. Error: {e}")

    # 2. Qdrant Setup
    print("\n2. Setting up Qdrant Vector Database...")
    try:
        init_vector_store()
        print("✅ Qdrant collection and policies verified.")
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant. Make sure the container is running. Error: {e}")
        
    print("\n--- Setup Complete ---")

if __name__ == "__main__":
    # Small delay to ensure docker containers are fully up if run immediately after docker-compose
    time.sleep(2)
    setup_databases()
