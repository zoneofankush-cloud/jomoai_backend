#=================================================================
#====================  ENV VARIABLE SETUP  =======================
from dotenv import load_dotenv
import os
load_dotenv()

DBConnection = os.getenv("DATA_BASE_URL")
if not DBConnection:
    raise ValueError("DATA_BASE_URL environment variable is not set")

#=================================================================
#=======================  Module Imports =========================
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from typing import Any, cast

async_pool = AsyncConnectionPool(
        conninfo=DBConnection,
        max_size=5,
        min_size=1,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False
    )

async def memory_saver_state():
    try:
        await async_pool.open()          
        saver = AsyncPostgresSaver(conn=cast(Any, async_pool))
        await saver.setup()             
        return saver
    except Exception as e:
        raise ValueError(f"Error creating memory saver state: {e}")

async def memory_store_state():
    try:
        await async_pool.open()          
        store = AsyncPostgresStore(conn=cast(Any, async_pool))
        await store.setup()    
        return store
    except Exception as e:
        raise ValueError(f"Error creating memory store state: {e}")