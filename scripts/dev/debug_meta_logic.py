import re

text = """![Image 0-0](imgs/cropped_page0_idx0.jpg)

## TEAM RECORDS AND SERIES NOTES

- UTSA fell to 4-5 overall and 2-3 in American Conference play. South Florida improved to 7-2 and 4-1.

This marked the second meeting and the series is now tied, 1-1."""

def extract_game_metadata(text):
    metadata = {"opponent_team": None, "home_away": "Home"}
    lines = text.split('\n')
    header = ""
    for line in lines:
        if line.startswith("# "):
            header = line[2:].strip()
            break
            
    # Fallback for opponent
    if not metadata["opponent_team"]:
        for line in lines[:30]:
            line = line.strip()
            fb_match = re.search(r"([^,.]+?)\s+improve[sd]\s+to", line, re.IGNORECASE)
            if fb_match:
                candidate = fb_match.group(1).strip()
                print(f"Candidate found: '{candidate}'")
                if "while " in candidate.lower():
                    candidate = re.split(r"\bwhile\b", candidate, flags=re.IGNORECASE)[-1].strip()
                    print(f"Candidate after while: '{candidate}'")
                
                if candidate.lower() not in ["utsa", "the roadrunners"]:
                    metadata["opponent_team"] = candidate
                    break
    return metadata

print(extract_game_metadata(text))
