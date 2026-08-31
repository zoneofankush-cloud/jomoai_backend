import bcrypt, sys, httpx, secrets, datetime as dt
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from security.jwt import get_jwt_token
from security.crypto_utils import encrypt_value, decrypt_value
from backend.user.user import fetch_id, email_exists
from dotenv import load_dotenv
import os
load_dotenv()
#=================================================================
#========================  PATH IMPORTS  =========================
from postgre.connection import async_pool

#=================================================================
#=======================  Module Imports =========================
from fastapi import Request, HTTPException, Depends, APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

GMAIL_CLIENT_ID = os.environ["GMAIL_CLIENT_ID"]
GMAIL_CLIENT_SECRET = os.environ["GMAIL_CLIENT_SECRET"]
STATE_TTL_SECONDS = 600


def generate_unusable_password_hash() -> str:
    """Gmail-only account ke liye — random, guess-proof, bcrypt-hashed
    placeholder. Login form se kabhi match nahi hoga, forgot-password
    se hi user apna real password set kar payega."""
    random_secret = secrets.token_urlsafe(32)
    return bcrypt.hashpw(random_secret.encode(), bcrypt.gensalt()).decode()


@router.get("/gmail/login")
async def gmail_login():
    state = secrets.token_urlsafe(32)
    async with async_pool.connection() as conn:
        await conn.execute(
            "INSERT INTO oauth_state (state, user_id) VALUES (%s, %s)",
            (state, uuid.uuid4()),
        )
    gmail_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GMAIL_CLIENT_ID}&state={state}&scope=openid email profile"
        f"&response_type=code&redirect_uri=https://jomoai.duckdns.org/gmail/callback"
    )
    return RedirectResponse(gmail_url)


@router.get("/gmail/callback")
async def gmail_callback(request: Request):
    error = request.query_params.get("error")
    if error:
        raise HTTPException(status_code=400, detail=f"Gmail authorization denied: {error}")

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

    new_user_id, created_at = row["user_id"], row["created_at"]
    if (dt.datetime.now(dt.timezone.utc) - created_at).total_seconds() > STATE_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="State expired")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GMAIL_CLIENT_ID,
                "client_secret": GMAIL_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": "https://jomoai.duckdns.org/gmail/callback"
            },
        )

        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="Token exchange failed")

        user_data = await client.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

    user = user_data.json()
    email = user.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Failed to retrieve user email from Gmail")

    gmail, existing_user_id, _ = await fetch_gmail_details(email)

    # Case 1: dono exist hain — direct login
    if gmail and await email_exists(email):
        token = await get_jwt_token(existing_user_id)
        return RedirectResponse(f"https://jomoai.pages.dev?token={token}&email={email}")

    # Case 3: gmail_oauth mein link tha, users row orphan/missing —
    # SAME existing_user_id se users row wapas banao, purana data preserve rahega
    if gmail and not await email_exists(email):
        placeholder_password = generate_unusable_password_hash()
        async with async_pool.connection() as conn:
            await conn.execute(
                "INSERT INTO public.users (id, email, password) VALUES (%s, %s, %s)",
                (existing_user_id, email, placeholder_password),
            )
        token = await get_jwt_token(existing_user_id)
        return RedirectResponse(f"https://jomoai.pages.dev?token={token}&email={email}")

    # Case 4: email password-user ke roop mein exist karta hai, gmail abhi link nahi —
    # password touch nahi, sirf link karo
    if await email_exists(email):
        existing_user_id = await fetch_id(email)
        await save_gmail_details(email, existing_user_id, access_token)
        token = await get_jwt_token(existing_user_id)
        return RedirectResponse(f"https://jomoai.pages.dev?token={token}&email={email}")

    # Case 2: dono nahi exist — bilkul naya user
    placeholder_password = generate_unusable_password_hash()
    async with async_pool.connection() as conn:
        await conn.execute(
            "INSERT INTO public.users (id, email, password) VALUES (%s, %s, %s)",
            (new_user_id, email, placeholder_password),
        )
    await save_gmail_details(email, new_user_id, access_token)
    token = await get_jwt_token(new_user_id)
    return RedirectResponse(f"https://jomoai.pages.dev?token={token}&email={email}")


#=================================================================
#=========================  DB HELPERS ============================
async def save_gmail_details(email: str, user_id, access_token: str):
    encrypted_token = await encrypt_value(access_token)
    async with async_pool.connection() as conn:
        await conn.execute(
            "INSERT INTO gmail_oauth (email, user_id, access_token, created_at) VALUES (%s, %s, %s, %s)",
            (email, user_id, encrypted_token, dt.datetime.now(dt.timezone.utc)),
        )

async def fetch_gmail_details(email: str):
    async with async_pool.connection() as conn:
        cur = await conn.execute(
            "SELECT email, user_id, access_token FROM gmail_oauth WHERE email = %s",
            (email,),
        )
        row = await cur.fetchone()
        if row is None:
            return None, None, None
        decrypted_token = await decrypt_value(row["access_token"])
        return row["email"], row["user_id"], decrypted_token

async def delete_gmail_details(email: str):
    async with async_pool.connection() as conn:
        await conn.execute(
            "DELETE FROM gmail_oauth WHERE email = %s",
            (email,),
        )
        return True

async def update_gmail_details(email: str, access_token: str):
    encrypted_token = await encrypt_value(access_token)
    async with async_pool.connection() as conn:
        await conn.execute(
            "UPDATE gmail_oauth SET access_token = %s, updated_at = NOW() WHERE email = %s",
            (encrypted_token, email),
        )
        return True