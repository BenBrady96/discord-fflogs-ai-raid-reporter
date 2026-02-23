import os
import requests

# FFLogs API V2 endpoints
TOKEN_URL = "https://www.fflogs.com/oauth/token"
API_URL = "https://www.fflogs.com/api/v2/client"

# Credentials from .env
CLIENT_ID = os.getenv("FFLOGS_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("FFLOGS_CLIENT_SECRET", "")

# Cached token
_access_token = None


def get_access_token():
    """Fetch an OAuth2 access token using client credentials."""
    global _access_token
    if _access_token:
        return _access_token

    response = requests.post(TOKEN_URL, auth=(CLIENT_ID, CLIENT_SECRET), data={
        "grant_type": "client_credentials",
    })
    response.raise_for_status()
    _access_token = response.json()["access_token"]
    return _access_token


def query(graphql_query, variables=None):
    """Execute a GraphQL query against the FFLogs API."""
    token = get_access_token()
    response = requests.post(
        API_URL,
        json={"query": graphql_query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    return response.json()


def get_report_data(report_code):
    """
    Fetch a full report summary from FFLogs including fight list and damage/healing tables.
    Returns a formatted text block ready for AI analysis.
    """
    # Step 1: Get all fights in the report
    fights_query = """
    query ($code: String!) {
        reportData {
            report(code: $code) {
                title
                startTime
                endTime
                fights(translate: true) {
                    id
                    name
                    kill
                    startTime
                    endTime
                    fightPercentage
                    difficulty
                }
            }
        }
    }
    """
    result = query(fights_query, {"code": report_code})
    report = result["data"]["reportData"]["report"]

    # Filter to boss fights only (difficulty > 0)
    boss_fights = [f for f in report["fights"] if f.get("difficulty") and f["difficulty"] > 0]

    if not boss_fights:
        return "No boss encounters found in this report."

    fight_ids = [f["id"] for f in boss_fights]

    # Step 2: Get damage and healing tables for all boss fights
    tables_query = """
    query ($code: String!, $fightIDs: [Int]!) {
        reportData {
            report(code: $code) {
                damageTable: table(fightIDs: $fightIDs, dataType: DamageDone)
                healingTable: table(fightIDs: $fightIDs, dataType: Healing)
                deathTable: table(fightIDs: $fightIDs, dataType: Deaths)
            }
        }
    }
    """
    tables_result = query(tables_query, {"code": report_code, "fightIDs": fight_ids})
    tables = tables_result["data"]["reportData"]["report"]

    # Step 3: Format into readable text
    output = []
    output.append(f"Report: {report['title']}")
    output.append(f"Total Boss Encounters: {len(boss_fights)}")

    kills = sum(1 for f in boss_fights if f["kill"])
    wipes = len(boss_fights) - kills
    output.append(f"Kills: {kills} | Wipes: {wipes}")
    output.append("")

    output.append("=== FIGHT BREAKDOWN ===")
    for fight in boss_fights:
        duration_ms = fight["endTime"] - fight["startTime"]
        minutes = int((duration_ms / 1000) // 60)
        seconds = int((duration_ms / 1000) % 60)
        status = "KILL" if fight["kill"] else f"WIPE ({fight.get('fightPercentage', '?')}%)"
        output.append(f"  {fight.get('name', 'Unknown')} — {status} — {minutes}m {seconds}s")

    if tables.get("damageTable") and tables["damageTable"].get("data"):
        output.append("")
        output.append("=== DAMAGE DONE ===")
        for entry in tables["damageTable"]["data"].get("entries", []):
            output.append(f"  {entry.get('name', 'Unknown')}: {entry.get('total', 0):,} total")

    if tables.get("healingTable") and tables["healingTable"].get("data"):
        output.append("")
        output.append("=== HEALING DONE ===")
        for entry in tables["healingTable"]["data"].get("entries", []):
            output.append(f"  {entry.get('name', 'Unknown')}: {entry.get('total', 0):,} total")

    if tables.get("deathTable") and tables["deathTable"].get("data"):
        output.append("")
        output.append("=== DEATHS ===")
        death_entries = tables["deathTable"]["data"].get("entries", [])
        output.append(f"  Total Deaths: {len(death_entries)}")

    return "\n".join(output)
