import re
from datetime import datetime

def extract_game_metadata(text):
    """
    Extract game-level metadata from the first header/section of the markdown.
    Format example:
    # 2024 UTSA Roadrunners Football UTSA vs. Tulsa Saturday, Oct. 26 H.A. Chapman Stadium·Tulsa, Okla. UTSA Postgame Notes
    """
    metadata = {
        "opponent_team": None,
        "game_date": None,
        "home_away": "Home",  # Default
        "conference": "American Athletic Conference",  # Default for UTSA 2024
    }

    # Focus on the first line or the first header
    lines = text.split('\n')
    header = ""
    for line in lines:
        if line.startswith("# "):
            header = line[2:].strip()
            break
    
    if not header:
        return metadata

    # 1. Extract opponent and home/away
    # Pattern 1: UTSA vs./at Opponent Team Day
    vs_match = re.search(r"UTSA\s+(vs\.|at)\s+([^,]+?)\s+(Saturday|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday)", header, re.IGNORECASE)
    if vs_match:
        rel = vs_match.group(1).lower()
        metadata["opponent_team"] = vs_match.group(2).strip()
        metadata["home_away"] = "Away" if rel == "at" else "Home"
    else:
        # Pattern 2: UTSA score, Opponent score (Bowl Games etc)
        # Example: UTSA 57, FIU 20 (First Responder Bowl)
        score_match = re.search(r"UTSA\s+\d+,\s+([^,]+?)\s+\d+", header, re.IGNORECASE)
        if score_match:
            metadata["opponent_team"] = score_match.group(1).split('(')[0].strip()

    # 2. Extract date
    date_match = re.search(r"(Saturday|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Z][a-z]+\.?\s+\d+)", header)
    if date_match:
        month_day = date_match.group(2).replace(".", "").strip()
        # Handle 'Sept' vs 'Sep'
        if month_day.startswith("Sept "):
            month_day = month_day.replace("Sept ", "Sep ")
        metadata["game_date_raw"] = month_day
        
    return metadata

def test_extract(header, season):
    print(f"Testing: {header}")
    meta = extract_game_metadata(header)
    if meta.get("game_date_raw"):
        try:
            raw_date = f"{meta['game_date_raw']} {season}"
            dt = datetime.strptime(raw_date, "%b %d %Y")
            meta["game_date"] = dt.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"Date error: {e}")
    print(f"Result: {meta}")
    print("-" * 20)

# Test cases
headers = [
    "# 2024 UTSA Roadrunners Football UTSA vs. Tulsa Saturday, Oct. 26 H.A. Chapman Stadium·Tulsa, Okla. UTSA Postgame Notes",
    "# 2025 UTSA Roadrunners Football UTSA at Temple Saturday, Sept. 27 Lincoln Financial Field·Philadelphia, Pa. UTSA Postgame Notes",
    "# 2025 UTSA Roadrunners Football UTSA 57, FIU 20 (First Responder Bowl) Friday, Dec. 26 Gerald J. Ford Stadium Dallas, Texas UTSA Postgame Notes"
]

for h in headers:
    test_extract(h, "2024" if "2024" in h else "2025")
