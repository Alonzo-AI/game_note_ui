"""
milvus_inserter.py
------------------
Handles embedding and insertion of chunks into the Milvus collection.
Uses BAAI/bge-large-en-v1.5 via SentenceTransformers.
"""

import os
import json
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection
from milvus_schema import connect_milvus

load_dotenv()

# --- Config -----------------------------------------------------------------
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "game_notes")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
BATCH_SIZE = 64  # Adjust based on memory

SCALAR_FIELDS = [
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
    "sport_code",
]


class MilvusInserter:
    def __init__(self, sport_code="mfb"):
        self.sport_code = sport_code.lower()
        connect_milvus(db_name=self.sport_code)
        self.collection = Collection(COLLECTION_NAME, using=self.sport_code)

        print(f"Loading embedding model '{EMBEDDING_MODEL_NAME}'...")
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    def embed_chunks(self, texts):
        """Generates embeddings for a list of strings."""
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    @staticmethod
    def _normalize_scalar(value):
        """Milvus scalar VARCHAR fields cannot receive None values."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value)

    def _prepare_batch_columns(self, batch):
        texts = [self._normalize_scalar(c.get("content", "")) for c in batch]
        vectors = self.embed_chunks(texts)

        metadata_columns = []
        for field in SCALAR_FIELDS:
            if field == "sport_code":
                metadata_columns.append([self.sport_code] * len(batch))
            else:
                metadata_columns.append([
                    self._normalize_scalar((c.get("metadata") or {}).get(field))
                    for c in batch
                ])

        return [vectors, texts, *metadata_columns]

    def insert_from_json(self, json_file_path):
        """Loads chunks from JSON and inserts them into Milvus."""
        print(f"Loading data from {json_file_path}...")

        with open(json_file_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        print(f"Processing {len(chunks)} chunks in batches of {BATCH_SIZE}...")

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i: i + BATCH_SIZE]

            data = self._prepare_batch_columns(batch)
            self.collection.insert(data)

            print(f"Inserted batch {i // BATCH_SIZE + 1} ({len(batch)} items)")

        self.collection.flush()
        print(f"Insertion complete. Total items in collection: {self.collection.num_entities}")


# --- Run script -------------------------------------------------------------

if __name__ == "__main__":
    sport_code = "wbb"
    team_name = "Colorado St."
    chunk_file_path = f"/home/ubuntu/workspace/suman/game_note_ui/data/{sport_code.upper()}/{team_name}_chunks_final.json"

    try:
        inserter = MilvusInserter(sport_code=sport_code)
        inserter.insert_from_json(chunk_file_path)
    except Exception as e:
        print(f"Error during insertion: {e}")