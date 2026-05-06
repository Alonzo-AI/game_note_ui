import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
# This name will appear in the MCP client
mcp = FastMCP("Game Note Search")

# Base URL for the FastAPI backend
# Ensure the backend is running on this port
BASE_URL = "http://3.145.61.23:8506"

@mcp.tool()
async def get_filter_options(sport_code: str = "mfb", team_name: str = None, opponent_team: str = None):
    """
    Get available filter options (teams, opponents, game dates) from the backend.
    
    Args:
        sport_code: The sport to filter by (e.g., 'mfb', 'mbb', 'wbb').
        team_name: Optional team name to narrow down opponents and dates.
        opponent_team: Optional opponent team name to narrow down game dates.
    """
    async with httpx.AsyncClient() as client:
        params = {"sport_code": sport_code}
        if team_name:
            params["team_name"] = team_name
        if opponent_team:
            params["opponent_team"] = opponent_team
            
        try:
            response = await client.get(f"{BASE_URL}/filter-options", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"Failed to fetch filter options: {str(e)}"}

@mcp.tool()
async def search_game_notes(
    message: str, 
    sport_code: str, 
    team_name: str, 
    opponent_team: str = None, 
    game_date: str = None
):
    """
    Search game notes and get an AI-generated answer based on the provided query and filters.
    
    Args:
        message: The search query or question about the game notes.
        sport_code: The sport code (e.g., 'mfb', 'mbb', 'wbb').
        team_name: The team name to focus on.
        opponent_team: Optional opponent team name to filter by.
        game_date: Optional specific game date (YYYY-MM-DD) to filter by.
    """
    async with httpx.AsyncClient() as client:
        payload = {
            "message": message,
            "sport_code": sport_code,
            "team_name": team_name,
            "opponent_team": opponent_team,
            "game_date": game_date
        }
        try:
            response = await client.post(f"{BASE_URL}/chat", json=payload, timeout=60.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"Search failed: {str(e)}"}

@mcp.tool()
async def get_pdf_info(college: str, season: str, game_id: str):
    """
    Get PDF metadata (total pages and URL) for a specific game note.
    
    Args:
        college: The college/team name.
        season: The season year.
        game_id: The specific game identifier (often the same as the source filename).
    """
    async with httpx.AsyncClient() as client:
        params = {"college": college, "season": season, "game_id": game_id}
        try:
            response = await client.get(f"{BASE_URL}/pdf-info", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"Failed to get PDF info: {str(e)}"}

if __name__ == "__main__":
    mcp.run()
