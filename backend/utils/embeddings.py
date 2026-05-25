import os
from langchain_community.vectorstores import Qdrant
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

# Connect to Qdrant (defaults to local docker instance)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "bank_policies"

def get_qdrant_client():
    return QdrantClient(url=QDRANT_URL)

def get_embeddings_model():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def init_vector_store():
    """Initializes Qdrant collection and uploads default policies if empty."""
    client = get_qdrant_client()
    embeddings = get_embeddings_model()
    
    # Check if collection exists
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if not exists:
        print(f"Creating Qdrant collection: {COLLECTION_NAME}...")
        # all-MiniLM-L6-v2 outputs 384-dimensional vectors
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        
        # Default policies to seed the knowledge base
        docs = [
            Document(page_content="Policy A1: Applicants with a DTI ratio over 0.5 must be placed in the subprime track or rejected.", metadata={"source": "policy"}),
            Document(page_content="Policy B2: Any history of bankruptcy within the last 7 years automatically flags the applicant as HIGH risk.", metadata={"source": "policy"}),
            Document(page_content="Policy C3: Missing minimum payments 3 times in a 12-month period is a critical behavioral risk.", metadata={"source": "policy"}),
            Document(page_content="Policy D4: Unverified income sources require manual review and flag as medium risk.", metadata={"source": "policy"}),
            Document(page_content="Policy E5: More than 5 credit inquiries in 12 months is considered credit-seeking behavior.", metadata={"source": "policy"})
        ]
        
        print("Uploading policies to Qdrant...")
        Qdrant.from_documents(
            docs,
            embeddings,
            url=QDRANT_URL,
            collection_name=COLLECTION_NAME,
        )
        print("Qdrant initialization complete.")
    else:
        print(f"Qdrant collection {COLLECTION_NAME} already exists.")

def search_knowledge_base(query: str, k: int = 3):
    """Searches the Qdrant vector database."""
    embeddings = get_embeddings_model()
    qdrant = Qdrant(
        client=get_qdrant_client(), 
        collection_name=COLLECTION_NAME, 
        embeddings=embeddings
    )
    
    # Qdrant returns similarity scores natively
    results_with_scores = qdrant.similarity_search_with_score(query, k=k)
    return results_with_scores
