import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# We use gemini-1.5-flash as the default model.
# It is fast and has a large context window, suitable for RAG and extraction.
def get_llm(temperature=0.0):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("GOOGLE_API_KEY is not set in environment variables.")
    
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=temperature,
        google_api_key=api_key,
    )
