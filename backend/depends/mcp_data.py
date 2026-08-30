import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from security.jwt import get_current_user
from postgre.connection import async_pool
from security.crypto_utils import encrypt_value, decrypt_value

router = APIRouter()

ALLOWED_PROVIDERS = {"github", "context7"}  # Add more providers as needed

class TokenData(BaseModel):
    mcp_name: str
    token: str

@router.post("/register_token")
async def register_token(data: TokenData, user_id: str = Depends(get_current_user)):
    mcp_name = data.mcp_name.lower()
    if mcp_name not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {mcp_name}")

    encrypted_token = await encrypt_value(data.token)
    try:
        async with async_pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO mcp_tokens (user_id, mcp_name, token)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, mcp_name)
                DO UPDATE SET token = EXCLUDED.token, updated_at = now()
                """,
                (user_id, mcp_name, encrypted_token),
            )
            await conn.commit()
        from tools.mcp_clients.basic import clear_mcp_cache
        clear_mcp_cache(user_id, mcp_name)
        return {"message": "Token registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update_token")
async def update_token(data: TokenData, user_id: str = Depends(get_current_user)):
    mcp_name = data.mcp_name.lower()
    if mcp_name not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {mcp_name}")

    encrypted_token = await encrypt_value(data.token)
    try:
        async with async_pool.connection() as conn:
            cur = await conn.execute(
                """
                UPDATE mcp_tokens
                SET token = %s, updated_at = now()
                WHERE user_id = %s AND mcp_name = %s
                """,
                (encrypted_token, user_id, mcp_name),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Token not found — use register instead")
            await conn.commit()
        from tools.mcp_clients.basic import clear_mcp_cache
        clear_mcp_cache(user_id, mcp_name)
        return {"message": "Token updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete_token")
async def delete_token(mcp_name: str, user_id: str = Depends(get_current_user)):
    mcp_name = mcp_name.lower()
    if mcp_name not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {mcp_name}")

    try:
        async with async_pool.connection() as conn:
            cur = await conn.execute(
                "DELETE FROM mcp_tokens WHERE user_id = %s AND mcp_name = %s",
                (user_id, mcp_name),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Token not found")
            await conn.commit()
        from tools.mcp_clients.basic import clear_mcp_cache
        clear_mcp_cache(user_id, mcp_name)
        return {"message": "Token deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_user_token(user_id: str, mcp_name: str):
    """Plain helper — koi FastAPI Depends nahi, isliye graph.py jaisi
    non-HTTP jagah se bhi direct call ho sakta hai."""
    mcp_name = mcp_name.lower()
    if mcp_name not in ALLOWED_PROVIDERS:
        return None
    async with async_pool.connection() as conn:
        cur = await conn.execute(
            "SELECT token FROM mcp_tokens WHERE user_id = %s AND mcp_name = %s",
            (user_id, mcp_name),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return await decrypt_value(row["token"])


@router.get("/get_token")
async def get_token(mcp_name: str, user_id: str = Depends(get_current_user)):
    token = await fetch_user_token(user_id, mcp_name)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"token": token}



# CREATE TABLE mcp_tokens (
#     user_id TEXT NOT NULL,
#     mcp_name TEXT NOT NULL,
#     token TEXT NOT NULL,
#     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
#     updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
#     PRIMARY KEY (user_id, mcp_name)
# );