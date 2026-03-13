import chromadb
from sentence_transformers import SentenceTransformer
from google import genai
from dotenv import load_dotenv
import os

# -----------------------------
# Load Environment Variables
# -----------------------------
load_dotenv()

# -----------------------------
# Config
# -----------------------------
COLLECTION_NAME = "game_notes"
EMBED_MODEL = "BAAI/bge-large-en-v1.5"
LLM_MODEL = "gemini-3-flash-preview"

# -----------------------------
# Initialize Gemini Client
# -----------------------------
gemini_client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY")
)

# -----------------------------
# Load Embedding Model
# -----------------------------
print("Loading embedding model...")
embed_model = SentenceTransformer(EMBED_MODEL)

# -----------------------------
# Connect to ChromaDB
# -----------------------------
chroma_client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = chroma_client.get_collection(
    name=COLLECTION_NAME
)

print("Connected to vector database")

# -----------------------------
# User Query
# -----------------------------
query = "ind all relevant information with a rushing yards against Tulsa from UTSA Quarterbacks?"

# Embed query
query_embedding = embed_model.encode(
    [query],
    normalize_embeddings=True
)

# -----------------------------
# Retrieve Top 5 Chunks
# -----------------------------
results = collection.query(
    query_embeddings=query_embedding.tolist(),
    n_results=5
)

retrieved_chunks = results["documents"][0]

# print("\nRetrieved Chunks:\n")

# for i, chunk in enumerate(retrieved_chunks):
#     print(f"Chunk {i+1}:")
#     print(chunk[:200])
#     print("------")

# -----------------------------
# Build Context
# -----------------------------
context = "\n\n".join(retrieved_chunks)

prompt = f"""
You are a sports analyst assistant.

Use ONLY the provided context to answer the question.

Context:
{context}

Question:
{query}

Answer clearly based only on the context.
"""

# -----------------------------
# Call Gemini
# -----------------------------
response = gemini_client.models.generate_content(
    model=LLM_MODEL,
    contents=prompt
)
print("query:", query)
print("\nLLM Answer:\n")
print(response.text)