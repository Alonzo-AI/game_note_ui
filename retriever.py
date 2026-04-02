from sentence_transformers import SentenceTransformer
from google import genai
from dotenv import load_dotenv
import os
from pymilvus import Collection
from milvus_schema import connect_milvus

# Load Environment Variables
load_dotenv()

# Config
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "game_notes")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "5"))
FILTER_OPTIONS_LIMIT = int(os.getenv("FILTER_OPTIONS_LIMIT", "10000"))
HEAD_TO_HEAD_SEARCH_LIMIT = int(os.getenv("HEAD_TO_HEAD_SEARCH_LIMIT", "12"))

# Initialize Gemini Client
gemini_client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY")
)

# Load Embedding Model
print("Loading embedding model...")
embed_model = SentenceTransformer(EMBED_MODEL)

print("Connecting to Milvus...")
connect_milvus()
collection = Collection(name=COLLECTION_NAME)
collection.load()

OUTPUT_FIELDS = [
    "content",
    "team",
    "opponent_team",
    "game_date",
    "home_away",
    "conference",
    "season",
    "game_id",
    "section",
    "title",
    "chunk_id",
]


def _escape_milvus_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_filter_expr(filters: dict | None) -> str | None:
    if not filters:
        return None

    clauses = []
    for key, value in filters.items():
        if value is None:
            continue
        normalized = str(value).strip()
        if not normalized:
            continue
        clauses.append(f'{key} == "{_escape_milvus_string(normalized)}"')

    return " and ".join(clauses) if clauses else None


def get_filter_options():
    rows = collection.query(
        expr="id >= 0",
        output_fields=["team", "opponent_team", "game_date"],
        limit=FILTER_OPTIONS_LIMIT,
    )

    teams = sorted({
        (row.get("team") or "").strip()
        for row in rows
        if (row.get("team") or "").strip()
    })
    opponents = sorted({
        (row.get("opponent_team") or "").strip()
        for row in rows
        if (row.get("opponent_team") or "").strip()
    })
    game_dates = sorted({
        (row.get("game_date") or "").strip()
        for row in rows
        if (row.get("game_date") or "").strip()
    })

    return {
        "team_names": teams,
        "opponent_team_names": opponents,
        "game_dates": game_dates,
    }

def get_answer(query: str, filters: dict = None):

    # Embed query
    query_embedding = embed_model.encode(
        [query],
        normalize_embeddings=True
    )

    filter_expr = _build_filter_expr(filters)

    opponent_filter = (filters or {}).get("opponent_team")
    search_limit = HEAD_TO_HEAD_SEARCH_LIMIT if opponent_filter else SEARCH_LIMIT

    results = collection.search(
        data=query_embedding.tolist(),
        anns_field="vector",
        param={
            "metric_type": "COSINE",
            "params": {"ef": 128},
        },
        limit=search_limit,
        expr=filter_expr,
        output_fields=OUTPUT_FIELDS
    )

    # Combine documents with their source metadata for context
    context_parts = []
    chunks_with_metadata = []

    hits = results[0] if results else []
    for i, hit in enumerate(hits):
        entity = hit.entity
        doc = entity.get("content")
        meta = {
            "team": entity.get("team"),
            "college": entity.get("team"),
            "opponent_team": entity.get("opponent_team"),
            "game_date": entity.get("game_date"),
            "home_away": entity.get("home_away"),
            "conference": entity.get("conference"),
            "season": entity.get("season"),
            "game_id": entity.get("game_id"),
            "source_file": entity.get("game_id"),
            "section": entity.get("section"),
            "title": entity.get("title"),
            "chunk_id": entity.get("chunk_id"),
            "distance": hit.distance,
        }

        source = meta.get("source_file") or "Unknown Source"
        # Store index in metadata for frontend mapping
        meta["citation_index"] = i + 1
        context_parts.append(
            "\n".join([
                f"Source [{i + 1}]: {source}",
                f"Season: {meta.get('season') or 'Unknown'}",
                f"Team: {meta.get('team') or 'Unknown'}",
                f"Opponent: {meta.get('opponent_team') or 'Unknown'}",
                f"Game Date: {meta.get('game_date') or 'Unknown'}",
                f"Section: {meta.get('section') or 'Unknown'}",
                doc,
            ])
        )
        chunks_with_metadata.append({
            "content": doc,
            "metadata": meta
        })

    context = "\n\n".join(context_parts)

    team_filter = (filters or {}).get("team")
    scope_instruction = ""
    if opponent_filter and team_filter:
        scope_instruction = f"""
    7. HEAD-TO-HEAD ONLY: The selected teams are "{team_filter}" and "{opponent_filter}". In "### Game by Game Notes", include ONLY games where these two teams played each other in the past. Do not add broader season summaries, unrelated opponents, or general achievements outside those meetings.
    8. IF EVIDENCE IS LIMITED: If the context only contains a few meetings, only summarize those meetings and say that the answer is limited to the retrieved head-to-head notes.
    """

    prompt = f"""
    You are a sports analyst assistant specializing in UTSA football history and statistics.

    Your goal is to extract the most impressive "nostalgia" information and milestones from the context provided. 

    Guidelines:
    1. PORTRAY TEAM IN A GOOD LIGHT: Highlight records broken, career highs, and historic streaks.
    2. STRUCTURE: Organize the data into clear, themed sections with bold headings (e.g., ### Historic Rushing Dominance, ### Individual Legacies).
    3. GAME BY GAME NOTES: Include a dedicated section titled "### Game by Game Notes". Within this section, create sub-sections for each specific game mentioned in the context, formatted as "#### [Team 1] vs [Team 2] ([Season])". Under each sub-section, highlight the amazing feats, interesting tidbits, or exceptional single-game stats specific to that match.
    4. HISTORICAL CONTEXT: Connect current stats to past legends or previous school records mentioned in the text (e.g., "The first since...", "Tied a record set in...").
    5. ACCURACY: Use ONLY the provided context.
    6. CITATION: When mentioning a specific fact, you MUST explicitly cite the source using its index number ONLY in brackets (e.g., "The Roadrunners tied the record [1]"). Do NOT use the chunk ID or file name in the text.
    {scope_instruction}

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
