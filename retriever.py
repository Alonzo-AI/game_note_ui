from sentence_transformers import SentenceTransformer
from google import genai
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv
import os
from pymilvus import Collection
from milvus_schema import connect_milvus

# Load Environment Variables
load_dotenv()

# Config
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "game_notes")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
LLM_MODEL = os.getenv("MODEL_NAME", "gemini-2.0-flash")
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
# connect_milvus() is now called dynamically in get_collection

def get_collection(sport_code: str):
    """
    Connect to the appropriate Milvus database and return the collection.
    """
    sport_code = sport_code.lower()
    connect_milvus(db_name=sport_code)
    coll = Collection(name=COLLECTION_NAME, using=sport_code)
    coll.load()
    return coll

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


def get_filter_options(sport_code: str = "mfb", team_name: str = None, opponent_team: str = None):
    collection = get_collection(sport_code)
    
    filters = {}
    if team_name:
        filters["team"] = team_name
    if opponent_team:
        filters["opponent_team"] = opponent_team
        
    expr = _build_filter_expr(filters) or "id >= 0"

    print(f"Fetching filter options for {sport_code} with expr: {expr}")
    rows = collection.query(
        expr=expr,
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

def get_answer(query: str, sport_code: str = "mfb", filters: dict = None):
    collection = get_collection(sport_code)

    # Embed query
    query_embedding = embed_model.encode(
        [query],
        normalize_embeddings=True
    )

    filter_expr = _build_filter_expr(filters)

    opponent_filter = (filters or {}).get("opponent_team")
    search_limit = HEAD_TO_HEAD_SEARCH_LIMIT if opponent_filter else SEARCH_LIMIT

    print(f"Searching Milvus with expr: {filter_expr} (limit={search_limit})...")
    try:
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
        print(f"Milvus search successful. Hits: {len(results[0]) if results else 0}")
    except Exception as e:
        print(f"Milvus search failed: {e}")
        import traceback
        traceback.print_exc()
        raise e

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
    game_date_filter = (filters or {}).get("game_date")
    scope_instruction = ""
    
    if opponent_filter and team_filter:
        scope_instruction += f"""
    7. HEAD-TO-HEAD ONLY: The selected teams are "{team_filter}" and "{opponent_filter}". In "### Game by Game Notes", include ONLY games where these two teams played each other in the past. Do not add broader season summaries, unrelated opponents, or general achievements outside those meetings.
    8. IF EVIDENCE IS LIMITED: If the context only contains a few meetings, only summarize those meetings and say that the answer is limited to the retrieved head-to-head notes.
    """
    
    if game_date_filter:
        scope_instruction += f"""
    9. DATE SPECIFIC: The user is interested in the game on {game_date_filter}. Focus your answer primarily on the performance and events of this specific day. In "### Game by Game Notes", ONLY include sub-sections for the game(s) occurring on {game_date_filter}. If the context contains statistical comparisons to other dates (e.g., "Season Highs" from other games), you may mention them briefly if they highlight the excellence of the current game, but do NOT create separate 'Buffalo vs X' subsections for those other dates.
    """

    prompt = f"""
    You are a sports analyst assistant specializing in college sports history and statistics.

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


    # Call Gemini with retry logic
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(Exception) # Catch general exceptions for retry
    )
    def generate_with_retry():
        print(f"Calling Gemini with model {LLM_MODEL}...")
        return gemini_client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt
        )

    try:
        response = generate_with_retry()
        print("Gemini call successful.")
    except Exception as e:
        print(f"Gemini API call failed after retries: {e}")
        import traceback
        traceback.print_exc()
        raise e
    
    return {
        "answer": response.text,
        "chunks": chunks_with_metadata,
        "prompt": prompt
    }
