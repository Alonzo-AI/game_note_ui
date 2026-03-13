import os
import re
import json
from pathlib import Path
from langchain_text_splitters import MarkdownHeaderTextSplitter


BASE_PATH = "output"


def remove_image_tags(text):
    """Remove markdown image tags"""
    return re.sub(r"!\[.*?\]\(.*?\)", "", text)


def load_markdown_files(college_name):
    """
    Load all markdown files for a college
    """
    college_path = Path(BASE_PATH) / college_name

    if not college_path.exists():
        raise ValueError(f"College folder not found: {college_path}")

    md_files = []

    for season_folder in college_path.iterdir():
        if season_folder.is_dir():

            season = season_folder.name

            for game_folder in season_folder.iterdir():
                if game_folder.is_dir():

                    for file in game_folder.glob("*.md"):

                        # Ignore hidden files like .filename.md
                        if file.name.startswith("."):
                            continue

                        md_files.append({
                            "file_path": str(file),
                            "season": season,
                            "game_id": game_folder.name
                        })

    return md_files


def find_page_number(chunk_content, layout_data):
    """
    Find the page number that best matches the chunk content.
    layout_data is a list of lists (one per page).
    """
    if not layout_data:
        return 1
    
    # Pre-calculate page texts
    page_texts = []
    for page in layout_data:
        page_text = " ".join([elem.get("content", "") for elem in page if elem.get("content")])
        page_texts.append(page_text.lower())
    
    chunk_lower = chunk_content.lower()
    
    best_page = 1
    max_overlap = -1
    
    for i, page_text in enumerate(page_texts):
        # Count how many words from chunk are in page_text
        words = chunk_lower.split()
        if not words: continue
        
        overlap = sum(1 for word in words if word in page_text)
        if overlap > max_overlap:
            max_overlap = overlap
            best_page = i + 1
            
    return best_page


def chunk_markdown(md_files, college_name):

    headers = [
        ("#", "title"),
        ("##", "section"),
        ("###", "subsection"),
    ]

    splitter = MarkdownHeaderTextSplitter(headers)

    all_chunks = []

    for file_info in md_files:

        try:
            with open(file_info["file_path"], "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            
            # Load corresponding layout JSON
            json_path = file_info["file_path"].replace(".md", ".json")
            layout_data = []
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    layout_data = json.load(f)
        except Exception as e:
            print(f"Skipping file due to error: {file_info['file_path']} → {e}")
            continue

        # Remove image markdown
        text = remove_image_tags(text)

        chunks = splitter.split_text(text)

        for i, chunk in enumerate(chunks):

            content = chunk.page_content.strip()

            # Ignore empty chunks
            if not content:
                continue
            
            page_num = find_page_number(content, layout_data)

            all_chunks.append({
                "content": content,
                "metadata": {
                    "college": college_name,
                    "season": file_info["season"],
                    "game_id": file_info["game_id"],
                    "chunk_id": f"chunk_{len(all_chunks)}",
                    "page_number": page_num,
                    **chunk.metadata
                }
            })

    return all_chunks


def save_chunks(chunks, college_name):

    output_file = f"{college_name}_chunks.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    print(f"\nAll chunks saved to: {output_file}")


def main():

    college_name = input("Enter college name: ").strip()

    md_files = load_markdown_files(college_name)

    print(f"\nFound {len(md_files)} markdown files")

    chunks = chunk_markdown(md_files, college_name)

    print(f"\nTotal chunks created: {len(chunks)}")

    save_chunks(chunks, college_name)

    # show one sample chunk
    if chunks:
        print("\nSample Chunk:\n")
        print(json.dumps(chunks[0], indent=2))


if __name__ == "__main__":
    main()