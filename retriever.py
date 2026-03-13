import chromadb
from sentence_transformers import SentenceTransformer
from google import genai
from dotenv import load_dotenv
import os

# Load Environment Variables
load_dotenv()

# Config
COLLECTION_NAME = "game_notes"
EMBED_MODEL = "BAAI/bge-large-en-v1.5"
LLM_MODEL = "gemini-2.0-flash"

# Initialize Gemini Client
gemini_client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY")
)

# Load Embedding Model
print("Loading embedding model...")
embed_model = SentenceTransformer(EMBED_MODEL)

def get_answer(query: str):
    # Connect to ChromaDB (Ensure fresh collection)
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    collection = chroma_client.get_collection(name=COLLECTION_NAME)

    # Embed query
    query_embedding = embed_model.encode(
        [query],
        normalize_embeddings=True
    )

    # Retrieve Top 5 Chunks
    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=5
    )

    retrieved_documents = results["documents"][0]
    retrieved_metadatas = results["metadatas"][0]
    
    # Combine documents with their source metadata for context
    context_parts = []
    chunks_with_metadata = []
    
    for i, (doc, meta) in enumerate(zip(retrieved_documents, retrieved_metadatas)):
        source = meta.get("source_file", "Unknown Source")
        # Store index in metadata for frontend mapping
        meta["citation_index"] = i + 1 
        context_parts.append(f"Source [{i + 1}]: {source}\n{doc}")
        chunks_with_metadata.append({
            "content": doc,
            "metadata": meta
        })

    context = "\n\n".join(context_parts)

    prompt = f"""
    You are a sports analyst assistant specializing in UTSA football history and statistics.

    Your goal is to extract the most impressive "nostalgia" information and milestones from the context provided. 

    Guidelines:
    1. PORTRAY TEAM IN A GOOD LIGHT: Highlight records broken, career highs, and historic streaks.
    2. STRUCTURE: Organize the data into clear, themed sections with bold headings (e.g., ### Historic Rushing Dominance, ### Individual Legacies).
    3. SUPERLATIVE PERFORMANCE: Include a dedicated section titled "### Superlative Performance". Within this section, create sub-sections for each specific game mentioned in the context, formatted as "#### [Team 1] vs [Team 2] ([Season])". Under each sub-section, highlight the amazing feats, interesting tidbits, or exceptional single-game stats specific to that match.
    4. HISTORICAL CONTEXT: Connect current stats to past legends or previous school records mentioned in the text (e.g., "The first since...", "Tied a record set in...").
    5. ACCURACY: Use ONLY the provided context. If a specific game (like UTSA vs. Tulsa) is mentioned in the query, prioritize those details while including the broader season achievements.
    6. CITATION: When mentioning a specific fact, you MUST explicitly cite the source using its index number ONLY in brackets (e.g., "The Roadrunners tied the record [1]"). Do NOT use the chunk ID or file name in the text.

    Context:
    {context}

    Question:
    {query}

    Answer clearly and enthusiastically based ONLY on the provided context, using Markdown formatting and inline bracket citations.
    """


    # Call Gemini
    response = gemini_client.models.generate_content(
        model=LLM_MODEL,
        contents=prompt
    )
    
    return {
        "answer": response.text,
        "chunks": chunks_with_metadata,
        "prompt": prompt
    }
