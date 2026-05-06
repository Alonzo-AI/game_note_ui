"""
predict_metadata.py
-------------------
Uses Gemini LLM to predict game-level metadata from a game-notes markdown file.
This metadata is identical across all chunks belonging to the same PDF/file.

Fields predicted:
    opponent_team  – Name of the opposing team
    game_date      – ISO date of the game  (YYYY-MM-DD)
    home_away      – "Home" or "Away"
    conference     – Conference the home team was playing in

Usage:
    from predict_metadata import predict_game_metadata

    metadata = predict_game_metadata(
        text        = markdown_text,
        team_name   = "UTSA",        # the home/primary team whose notes these are
        season      = "2024",        # optional year hint
    )
"""

import os
import json
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

_API_KEY   = os.getenv("GOOGLE_API_KEY")
_MODEL     = "gemini-3-flash-preview"
_client    = genai.Client(api_key=_API_KEY) if _API_KEY else None

def _build_system_prompt(team_name: str) -> str:
    """Build the system prompt, embedding the primary team name for better context."""
    team_line = f"Primary team (whose postgame notes these are): {team_name}\n" if team_name else ""
    return (
        f"You are an expert sports data extractor.\n"
        f"{team_line}"
        "Given a college football postgame notes document (Markdown), extract exactly\n"
        "four fields that apply to the ENTIRE document.\n\n"
        "Return ONLY a valid JSON object — no markdown, no extra text:\n"
        "{\n"
        '  "opponent_team": "<name of the opposing team>",\n'
        '  "game_date":     "<ISO-8601 date, e.g. 2024-10-26, or null if unknown>",\n'
        '  "home_away":     "<\'Home\' if the primary team hosted, \'Away\' otherwise>",\n'
        '  "conference":    "<conference name the primary team belongs to, or null>"\n'
        "}\n\n"
        "Rules:\n"
        f"- opponent_team : the team that {team_name or 'the primary team'} played against. "
        f"Never return '{team_name or 'the primary team'}' itself.\n"
        "- game_date     : use the season year hint when the year is not explicit in the text.\n"
        "- home_away     : 'Away' for road games AND neutral-site / bowl games.\n"
        "- conference    : infer from the text (e.g. 'American Athletic Conference', 'Conference USA', 'SEC').\n"
        "- Use null for any field you cannot determine with confidence.\n"
    )


def predict_game_metadata(text: str, team_name: str = "", season: str = "") -> dict:
    """
    Predict game-level metadata using Gemini LLM.

    Parameters
    ----------
    text      : Full markdown content of the PDF.
    team_name : Primary team name (e.g. "UTSA", "Texas", "Alabama").
    season    : Season year string (e.g. "2024") as a hint for game_date.

    Returns
    -------
    dict with keys: opponent_team, game_date, home_away, conference
    """
    fallback = {
        "opponent_team": None,
        "game_date":     None,
        "home_away":     "Home",
        "conference":    None,
    }

    if not _client:
        print("  [predict_metadata] GOOGLE_API_KEY not set — skipping LLM call.")
        return fallback

    # Build user prompt — season hint here, team_name is already in the system prompt
    season_hint = f"  (Season year: {season})\n" if season else ""
    prompt = (
        f"Extract the game metadata from the postgame notes below.{season_hint}\n"
        f"---\n{text[:3000].strip()}\n---"
    )

    import time
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_build_system_prompt(team_name),
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )

            raw = response.text.strip()
            # Strip any accidental markdown fences
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE)

            parsed = json.loads(raw)

            # Validate home_away value
            home_away = parsed.get("home_away", "Home")
            if home_away not in ("Home", "Away"):
                home_away = "Home"

            return {
                "opponent_team": parsed.get("opponent_team") or fallback["opponent_team"],
                "game_date":     parsed.get("game_date")     or fallback["game_date"],
                "home_away":     home_away,
                "conference":    parsed.get("conference")    or fallback["conference"],
            }

        except Exception as exc:
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                if attempt < max_retries - 1:
                    print(f"  [predict_metadata] Rate limit hit (429). Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
            print(f"  [predict_metadata] LLM call failed: {exc}")
            break

    return fallback
