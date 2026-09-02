import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import datetime
import json
from postgre.connection import async_pool
from security.redis_connection import async_redis

import json
async def check_ownership(thread_id, user_id):
    redis_row = await async_redis.get(f"ownership:{user_id}{thread_id}")
    if redis_row:
        return json.load(redis_row) # type: ignore
    async with async_pool.connection() as conn:
        cur = await conn.execute("SELECT thread_id, title FROM threads WHERE thread_id = %s AND user_id = %s", (thread_id, user_id,),)
        row = await cur.fetchone()
        if row is not None:
            await async_redis.set(f"ownership:{user_id}{thread_id}", json.dumps(row, default=list))
        return row

async def email_exists(email: str) -> bool:
    async with async_pool.connection() as conn:
        cur = await conn.execute("SELECT 1 FROM public.users WHERE email = %s", (email,))
        email_id = await cur.fetchone()
        return email_id is not None

async def password_fetcher(email: str):
    async with async_pool.connection() as conn:
        cur = await conn.execute("SELECT password FROM public.users WHERE email = %s", (email,))
        password = await cur.fetchone()
    if password is None:
        return None
    else:
        return password['password']

async def fetch_id(email):
    async with async_pool.connection() as conn:
        curr = await conn.execute("SELECT id FROM public.users WHERE email = %s", (email,))
        id = await curr.fetchone()
        if id is None:
               return None
        else:
            return id['id']

