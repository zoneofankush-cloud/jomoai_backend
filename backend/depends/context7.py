import sys, httpx, secrets, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
import os, hashlib, base64, secrets
load_dotenv()

from security.jwt import verify_query_token
from backend.depends.mcp_data import register_token, TokenData
from postgre.connection import async_pool

from fastapi import Request, HTTPException, Depends, APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

CONTEXT7_CLIENT_ID = os.environ["CONTEXT7_CLIENT_ID"]
VERIFIER = os.environ["CONTEXT7_VERIFIER"]
STATE_TTL_SECONDS = 600


@router.get("/context7/login")
async def context7_login(user_id: str = Depends(verify_query_token)):
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(32)
    async with async_pool.connection() as conn:
        await conn.execute(
            "INSERT INTO oauth_state (state, user_id) VALUES (%s, %s)",
            (state, user_id),
        )
    context7_url = (
            f"https://context7.com/api/oauth/authorize"
            f"?response_type=code&client_id={CONTEXT7_CLIENT_ID}"
            f"&redirect_uri=https://jomoai.duckdns.org/context7/callback"
            f"&code_challenge={code_challenge}&code_challenge_method=S256"
            f"&state={state}"
            )
    return RedirectResponse(context7_url)

@router.get("/context7/callback")
async def context7_callback(request: Request):
    error = request.query_params.get("error")
    if error:
        raise HTTPException(status_code=400, detail=f"Context7 authorization denied: {error}")

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
                "https://context7.com/api/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": VERIFIER,
                    "redirect_uri": "https://jomoai.duckdns.org/context7/callback",
                    "client_id": CONTEXT7_CLIENT_ID,
                },
            )

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Token exchange failed")

    await register_token(TokenData(mcp_name="context7", token=access_token), user_id=stored_user_id)

    return RedirectResponse("https://jomoai.pages.dev/settings/integrations?connected=context7")