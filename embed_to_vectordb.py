import json
import chromadb
from sentence_transformers import SentenceTransformer

# -----------------------------
# Config
# -----------------------------
CHUNKS_FILE = "UTSA_chunks.json"
COLLECTION_NAME = "game_notes"
MODEL_NAME = "BAAI/bge-large-en-v1.5"
DB_PATH = "./chroma_db"

# -----------------------------
# Load Embedding Model
# -----------------------------
print("Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)
print("Model loaded")

# -----------------------------
# Load Chunk Data
# -----------------------------
print("Loading chunks...")

with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)

print(f"Total chunks loaded: {len(chunks)}")

# -----------------------------
# Connect to ChromaDB
# -----------------------------
client = chromadb.PersistentClient(path=DB_PATH)

# -----------------------------
# Drop Existing Collection
# -----------------------------
existing_collections = [c.name for c in client.list_collections()]

if COLLECTION_NAME in existing_collections:
    print(f"Dropping existing collection: {COLLECTION_NAME}")
    client.delete_collection(COLLECTION_NAME)

# -----------------------------
# Create Fresh Collection
# -----------------------------
collection = client.get_or_create_collection(name=COLLECTION_NAME)

print("New collection created")

# -----------------------------
# Prepare Documents
# -----------------------------
documents = []
metadatas = []
ids = []

for i, chunk in enumerate(chunks):

    text = chunk.get("content", "")
    metadata = chunk.get("metadata", {})

    college = metadata.get("college")
    season = metadata.get("season")
    section = metadata.get("section")
    source_file = metadata.get("game_id")

    # Build embedding text
    enriched_text = f"""
Team: {college}
Season: {season}
Section: {section}

{text}
"""

    documents.append(enriched_text)

    # Clean metadata (Chroma only allows simple types)
    clean_metadata = {}

    if college is not None:
        clean_metadata["college"] = str(college)

    if season is not None:
        clean_metadata["season"] = str(season)

    if section is not None:
        clean_metadata["section"] = str(section)

    if source_file is not None:
        clean_metadata["source_file"] = str(source_file)

    chunk_id = metadata.get("chunk_id")
    if chunk_id is not None:
        clean_metadata["chunk_id"] = str(chunk_id)

    page_number = metadata.get("page_number")
    if page_number is not None:
        clean_metadata["page_number"] = int(page_number)

    metadatas.append(clean_metadata)

    ids.append(f"chunk_{i}")

print(f"Prepared {len(documents)} documents for embedding")

# -----------------------------
# Generate Embeddings
# -----------------------------
print("Generating embeddings...")

embeddings = model.encode(
    documents,
    show_progress_bar=True,
    normalize_embeddings=True
)

print("Embeddings generated")

# -----------------------------
# Store in Vector DB
# -----------------------------
print("Storing vectors in ChromaDB...")

collection.add(
    documents=documents,
    embeddings=embeddings.tolist(),
    metadatas=metadatas,
    ids=ids
)

print("Vector database indexing completed successfully")

# -----------------------------
# Quick Debug Retrieval
# -----------------------------
# print("\nRunning sample retrieval test...")

# query = "UTSA offensive performance"

# query_embedding = model.encode(
#     ["Represent this sentence for searching relevant passages: " + query],
#     normalize_embeddings=True
# )

# results = collection.query(
#     query_embeddings=query_embedding.tolist(),
#     n_results=2
# )

# print("\nSample Retrieval Results:\n")

# for i, doc in enumerate(results["documents"][0]):
#     print(f"Result {i+1}:")
#     print(doc[:300])
#     print("------")