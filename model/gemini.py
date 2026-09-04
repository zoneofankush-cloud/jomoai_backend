# BackEnd/model/gemini.py

import os
from dotenv import load_dotenv
load_dotenv()

#=================================================================
#=======================  Module Imports =========================
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.globals import set_llm_cache
from langchain_community.cache import AsyncRedisCache

# Tera existing redis connection import kiya
from security.redis_connection import async_redis

#=================================================================
#=======================  CACHE SETUP ============================
# 1 din (86400s) ka TTL rakha hai taaki purana cache Redis ko full na kare
set_llm_cache(AsyncRedisCache(redis_=async_redis, ttl=82800))

#=================================================================
#=======================  JOMO AI SETUP ==========================

# Use Vertex AI for the default JOMO AI model
jomoai = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    vertexai=True,
    project="project-45267852-1c84-4327-ba7",
    location="global",
    streaming=True
)