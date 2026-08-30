import sys, httpx, secrets, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
import os
load_dotenv()
#=================================================================
#========================  PATH IMPORTS  =========================
from security.jwt import verify_query_token
from backend.depends.mcp_data import register_token, TokenData
from postgre.connection import async_pool

#=================================================================
#=======================  Module Imports =========================
from fastapi import Request, HTTPException, Depends, APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
STATE_TTL_SECONDS = 600

@router.get("/github/login")
async def github_login(user_id: str = Depends(verify_query_token)):
    state = secrets.token_urlsafe(32)
    async with async_pool.connection() as conn:
        await conn.execute(
            "INSERT INTO oauth_state (state, user_id) VALUES (%s, %s)",
            (state, user_id),
        )
    github_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={CLIENT_ID}&state={state}&scope=repo"
    )
    return RedirectResponse(github_url)

@router.get("/callback")
async def github_callback(request: Request):
    error = request.query_params.get("error")
    if error:
        raise HTTPException(status_code=400, detail=f"GitHub authorization denied: {error}")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    async with async_pool.connection() as conn:
        cur = await conn.execute(
            "DELETE FROM oauth_state WHERE state = %s RETURNING user_id, created_at",
            (state,),
        )
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    stored_user_id, created_at = row["user_id"], row["created_at"]
    if (dt.datetime.now(dt.timezone.utc) - created_at).total_seconds() > STATE_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="State expired")
    

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
            },
        )

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Token exchange failed")

    await register_token(TokenData(mcp_name="github", token=access_token), user_id=stored_user_id)

    return RedirectResponse("https://jomoai.pages.dev/settings/integrations?connected=github")

# CREATE TABLE oauth_state (
#     state TEXT PRIMARY KEY,
#     user_id TEXT NOT NULL,
#     created_at TIMESTAMPTZ NOT NULL DEFAULT now()
# );