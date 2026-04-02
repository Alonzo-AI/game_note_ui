"""
milvus_schema.py
----------------
Defines the Milvus collection schema for game notes.
This file is responsible for creating the collection and indices.
"""

import os
from dotenv import load_dotenv
from pymilvus import (
    connections,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    utility
)

load_dotenv()

# --- Config -----------------------------------------------------------------
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "game_notes")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

def connect_milvus():
    print(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}...")
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)

def create_game_notes_collection():
    """
    Creates the game_notes collection with a production-ready schema.
    """
    if utility.has_collection(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' already exists. Dropping for fresh setup...")
        utility.drop_collection(COLLECTION_NAME)

    # 1. Define Fields
    fields = [
        # Primary Key
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        
        # Dense Vector
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        
        # Raw Content
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=12000),
        
        # Metadata fields (Filtering)
        FieldSchema(name="team", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="opponent_team", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="game_date", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="home_away", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="conference", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="season", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="game_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="section", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="sport_code", dtype=DataType.VARCHAR, max_length=32),
    ]

    schema = CollectionSchema(fields, description="College Football Game Notes Chunks")
    
    print(f"Creating collection '{COLLECTION_NAME}'...")
    collection = Collection(name=COLLECTION_NAME, schema=schema)

    # 2. Create Indices
    print("Creating indices...")
    
    # Vector Index (HNSW for production performance)
    vector_index_params = {
        "index_type": "HNSW",
        "metric_type": "COSINE", # Typically best for BGE models
        "params": {"M": 16, "efConstruction": 200},
    }
    collection.create_index(field_name="vector", index_params=vector_index_params)
    
    # Scalar Indices (For fast filtering)
    # We create indices for fields used in common queries
    collection.create_index(field_name="team", index_name="idx_team")
    collection.create_index(field_name="opponent_team", index_name="idx_opponent")
    collection.create_index(field_name="game_date", index_name="idx_game_date")
    collection.create_index(field_name="conference", index_name="idx_conference")
    collection.create_index(field_name="game_id", index_name="idx_game_id")
    collection.create_index(field_name="season", index_name="idx_season")

    print(f"Collection '{COLLECTION_NAME}' setup complete.")
    return collection

if __name__ == "__main__":
    try:
        connect_milvus()
        create_game_notes_collection()
    except Exception as e:
        print(f"Failed to setup Milvus: {e}")
