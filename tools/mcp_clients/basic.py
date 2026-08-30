import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain_mcp_adapters.client import MultiServerMCPClient
from backend.depends.mcp_data import fetch_user_token
import time as _time

_mcp_tools_cache: dict[tuple[str, str], tuple[float, list]] = {}
MCP_TOOLS_TTL = 300

# NOTE: GitHub MCP tools abhi unfiltered hain (X-MCP-Tools se tools sirf 6 tak
# limit kiye hain, but result payload trim nahi kiya). Desktop app phase mein
# if/else based selective tool exposure aur result trimming dono add karna hai.
PROVIDER_CONFIGS = {
    "github": {
        "url": "https://api.githubcopilot.com/mcp/",
        "transport": "streamable_http",
        "tools": "get_me,search_repositories,get_file_contents,list_issues,list_pull_requests,get_commit"
    },
    "context7": {
            "transport": "streamable_http",
            "url": "https://mcp.context7.com/mcp",
        }
}

async def get_mcp_tools(mcp_name: str, access_token: str):
    cfg = PROVIDER_CONFIGS.get(mcp_name)
    if not cfg or not access_token:
        return []
    headers = {"Authorization": f"Bearer {access_token}"}
    if "tools" in cfg:
        headers["X-MCP-Tools"] = cfg["tools"]

    client = MultiServerMCPClient({
        mcp_name: {
            "transport": cfg["transport"],
            "url": cfg["url"],
            "headers": headers
        }
    }) # type: ignore
    try:
        return await client.get_tools()
    except Exception as e:
        print(f"Warning: MCP '{mcp_name}' tools failed ->", e)
        return []

async def get_mcp_tools_for_user(user_id: str, mcp_name: str):
    key = (user_id, mcp_name)
    cached = _mcp_tools_cache.get(key)
    if cached and (_time.time() - cached[0] < MCP_TOOLS_TTL):
        return cached[1]
    token = await fetch_user_token(user_id, mcp_name)
    tools_list = await get_mcp_tools(mcp_name, token) # type: ignore
    _mcp_tools_cache[key] = (_time.time(), tools_list)
    return tools_list

def clear_mcp_cache(user_id: str, mcp_name: str):
    key = (user_id, mcp_name)
    if key in _mcp_tools_cache:
        del _mcp_tools_cache[key]
