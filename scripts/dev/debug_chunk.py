from chunk_raw_data import chunk_markdown, save_chunks
from pathlib import Path

# Mock file_info
file_info = {
    "file_path": "/home/ubuntu/workspace/suman/game_note_ui/output/UTSA/2024/9MAxXdpZ9Raa4OeOItrVM2GbVgzH5D4wL89SHLMJ/9MAxXdpZ9Raa4OeOItrVM2GbVgzH5D4wL89SHLMJ.md",
    "season": "2024",
    "game_id": "9MAxXdpZ9Raa4OeOItrVM2GbVgzH5D4wL89SHLMJ"
}

chunks = chunk_markdown([file_info], "UTSA")
print(f"Created {len(chunks)} chunks")
if chunks:
    print(chunks[0]["metadata"])
