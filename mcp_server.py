import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Base URL for the FastAPI backend
# Ensure the backend is running on this port
BASE_URL = "http://3.145.61.23:8506"

def build_mcp() -> FastMCP:
    """
    Build and return a new FastMCP instance with all tools registered.

    Important for AWS Lambda:
    - The streamable HTTP session manager behind FastMCP is stateful and expects its
      lifespan to run once per instance. Creating a fresh FastMCP per invoke avoids
      'run() can only be called once' errors.
    """

    # Lambda note:
    # FastMCP enables DNS rebinding protection when transport_security is set.
    # In Lambda Function URLs the Host header is the lambda-url domain, so we either:
    # - explicitly allow it, or
    # - disable host/origin validation.
    #
    # For now we disable it by default (can be tightened by setting MCP_ALLOWED_HOSTS).
    import os

    allowed_hosts_env = os.getenv("MCP_ALLOWED_HOSTS", "").strip()
    if allowed_hosts_env:
        allowed_hosts = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]
        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=[],
        )
    else:
        transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    # Initialize FastMCP server (name shows in MCP clients)
    mcp = FastMCP(
        "Game Note Search",
        transport_security=transport_security,
        # Lambda handlers are inherently stateless across HTTP invokes.
        # This avoids session-id coupling ("Session not found") between requests.
        stateless_http=True,
    )

    @mcp.tool()
    async def get_filter_options(
        sport_code: str = "mfb", team_name: str | None = None, opponent_team: str | None = None
    ):
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
        opponent_team: str | None = None,
        game_date: str | None = None,
        month_day: str | None = None,
    ):
        """
        Search game notes and get an AI-generated answer based on the provided query and filters.

        Args:
            message: The search query or question about the game notes.
            sport_code: The sport code (e.g., 'mfb', 'mbb', 'wbb').
            team_name: The team name to focus on.
            opponent_team: Optional opponent team name to filter by.
            game_date: Optional specific game date (YYYY-MM-DD) to filter by.
            month_day: Optional month-day (MM-DD) to search across all seasons.
        """
        async with httpx.AsyncClient() as client:
            payload = {
                "message": message,
                "sport_code": sport_code,
                "team_name": team_name,
                "opponent_team": opponent_team,
                "game_date": game_date,
                "month_day": month_day,
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

    return mcp

if __name__ == "__main__":
    build_mcp().run()
