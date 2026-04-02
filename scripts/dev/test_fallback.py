import re

line = "- UTSA fell to 4-5 overall and 2-3 in American Conference play. South Florida improved to 7-2 and 4-1."
fb_match = re.search(r"UTSA\s+(?:falls|fell)\s+.*?while\s+([^,]+?)\s+improves", line, re.IGNORECASE)
if not fb_match:
    fb_match = re.search(r"UTSA\s+(?:falls|fell)\s+.*?\.\s+([^,]+?)\s+improved", line, re.IGNORECASE)

if fb_match:
    print(f"Match: {fb_match.group(1)}")
else:
    print("No match")

line2 = "- UTSA falls to 2-3,0-1, while Temple improves to 3-2,1-0"
fb_match2 = re.search(r"UTSA\s+(?:falls|fell)\s+.*?while\s+([^,]+?)\s+improves", line2, re.IGNORECASE)
if fb_match2:
    print(f"Match 2: {fb_match2.group(1)}")
else:
    print("No match 2")
