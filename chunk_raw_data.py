"""
chunk_raw_data.py
-----------------
Loads markdown game-note files, predicts per-file metadata via LLM,
then splits each file into chunks and saves them to a JSON file.

Steps:
  1. Load all .md files under  output/<team_name>/<season>/<game_id>/
  2. For each file: predict metadata (opponent, date, home/away, conference) — once per file.
  3. Split the markdown text into chunks.
  4. Attach the metadata to every chunk from that file.
  5. Save all chunks to <team_name>_chunks.json

Run:
    python chunk_raw_data.py
"""

import os
import re
import json
import time
from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from predict_metadata import predict_game_metadata


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_PATH = "output"

HEADERS = [
    ("#",   "title"),
    ("##",  "section"),
    ("###", "subsection"),
]

# Max characters per chunk. 
# We'll split any header-based chunk that exceeds this.
CHUNK_MAX_SIZE = 1500
CHUNK_OVERLAP = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def remove_image_tags(text: str) -> str:
    """Strip markdown image syntax: ![alt](url)"""
    return re.sub(r"!\[.*?\]\(.*?\)", "", text)


def load_markdown_files(team_name: str, sport_code: str) -> list[dict]:
    """
    Walk the markdown tree for both supported layouts:
        1. output/<sport_code>/<team_name>/<season>/<game_id>/*.md
        2. output/<sport_code>/<team_name>/<season>/*.md

    Return a list of:
        { file_path, season, game_id }
    """
    team_path = Path(BASE_PATH) / sport_code / team_name
    if not team_path.exists():
        raise FileNotFoundError(f"Team folder not found: {team_path}")

    files = []
    for season_dir in sorted(team_path.iterdir()):
        if not season_dir.is_dir():
            continue

        # Newer layout: one folder per game_id containing the markdown file.
        for game_dir in sorted(season_dir.iterdir()):
            if not game_dir.is_dir():
                continue
            for md_file in sorted(game_dir.glob("*.md")):
                if md_file.name.startswith(".") or md_file.name.startswith("._"):
                    continue
                files.append({
                    "file_path": str(md_file),
                    "season":    season_dir.name,
                    "game_id":   game_dir.name,
                })

        # Older layout: markdown files live directly under the season folder.
        for md_file in sorted(season_dir.glob("*.md")):
            if md_file.name.startswith(".") or md_file.name.startswith("._"):
                continue
            files.append({
                "file_path": str(md_file),
                "season": season_dir.name,
                "game_id": md_file.stem,
            })

    return files


def chunk_file(text: str) -> list:
    """
    Split markdown text into chunks.
    1. First split by headers.
    2. Then further split large sections recursively.
    """
    # Step 1: Split by headers
    header_splitter = MarkdownHeaderTextSplitter(HEADERS)
    header_chunks = header_splitter.split_text(text)
    
    # Step 2: Split large chunks recursively
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_MAX_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )
    
    final_docs = []
    for doc in header_chunks:
        if len(doc.page_content) > CHUNK_MAX_SIZE:
            # Split the long section
            sub_docs = recursive_splitter.split_documents([doc])
            final_docs.extend(sub_docs)
        else:
            final_docs.append(doc)
            
    return final_docs


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process(team_name: str, sport_code: str) -> list[dict]:
    """
    Full pipeline: load → predict metadata → chunk → attach metadata.
    Returns a flat list of chunk dicts ready to save.
    """
    md_files = load_markdown_files(team_name, sport_code)
    print(f"Found {len(md_files)} markdown files for '{team_name}'.")

    all_chunks = []

    for i, file_info in enumerate(md_files, start=1):
        file_path = file_info["file_path"]
        season    = file_info["season"]
        game_id   = file_info["game_id"]

        print(f"[{i}/{len(md_files)}] {file_path}")
        time.sleep(2)  # Delay to avoid rate limiting

        try:
            text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            text = remove_image_tags(text)

            # --- Step 1: Predict metadata for this file (once per file) ------
            print(f"  Predicting metadata...", flush=True)
            metadata = predict_game_metadata(text, team_name=team_name, season=season)
            print(f"  → {metadata}", flush=True)

            # --- Step 2: Split into chunks ------------------------------------
            chunks = chunk_file(text)
            print(f"  → {len(chunks)} chunks")

            # --- Step 3: Build chunk records, appending the predicted metadata --
            for chunk in chunks:
                all_chunks.append({
                    "content": chunk.page_content,
                    "metadata": {
                        # File-level identifiers
                        "team":    team_name,
                        "season":  season,
                        "game_id": game_id,
                        "chunk_id": f"chunk_{len(all_chunks)}",
                        # LLM-predicted game metadata (same for every chunk in this file)
                        "opponent_team": metadata["opponent_team"],
                        "game_date":     metadata["game_date"],
                        "home_away":     metadata["home_away"],
                        "conference":    metadata["conference"],
                        # Header metadata from the splitter (title / section / subsection)
                        **chunk.metadata,
                    },
                })

        except Exception as exc:
            print(f"  ERROR — skipping file: {exc}")
            continue

    return all_chunks


def save(chunks: list[dict], team_name: str, sport_code: str) -> None:
    output_dir = Path(f"data/{sport_code}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"{team_name}_chunks_final.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(chunks)} chunks → {output_file}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    team_name = "Colorado St."
    sport_code = "WBB"       # ← change this to process a different team

    chunks = process(team_name, sport_code)
    print(f"\nTotal chunks: {len(chunks)}")
    save(chunks, team_name, sport_code)

    if chunks:
        print("\nSample chunk:")
        print(json.dumps(chunks[0], indent=2, ensure_ascii=False))
