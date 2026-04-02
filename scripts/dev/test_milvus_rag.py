import argparse
import json

from retriever import get_answer


def main():
    parser = argparse.ArgumentParser(description="Quick test script for Milvus RAG retrieval.")
    parser.add_argument("query", help="Natural language query to search against game notes.")
    parser.add_argument("--opponent-name", dest="opponent_name", help="Optional opponent team filter.")
    parser.add_argument("--game-date", dest="game_date", help="Optional game date filter in YYYY-MM-DD format.")
    parser.add_argument("--show-prompt", action="store_true", help="Print the full LLM prompt.")
    args = parser.parse_args()

    filters = {}
    if args.opponent_name:
        filters["opponent_team"] = args.opponent_name
    if args.game_date:
        filters["game_date"] = args.game_date

    result = get_answer(args.query, filters=filters or None)

    print("\n=== Filters ===")
    print(json.dumps(filters, indent=2) if filters else "None")

    print("\n=== Answer ===")
    print(result["answer"])

    print("\n=== Retrieved Chunks ===")
    for chunk in result["chunks"]:
        meta = chunk["metadata"]
        print(
            f"[{meta.get('citation_index')}] "
            f"season={meta.get('season')} "
            f"opponent={meta.get('opponent_team')} "
            f"game_date={meta.get('game_date')} "
            f"game_id={meta.get('game_id')}"
        )
        print(chunk["content"][:400].strip())
        print("-" * 80)

    if args.show_prompt:
        print("\n=== Prompt ===")
        print(result["prompt"])


if __name__ == "__main__":
    main()
