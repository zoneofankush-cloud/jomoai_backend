from langchain.tools import tool
from youtube_search import YoutubeSearch
import asyncio
import json

@tool
async def search_youtube(query: str, number: int):
    """Search YouTube for a given query and number of search results."""
    def search_youtube():
        results = YoutubeSearch(query,number).to_json()
        data = json.loads(results)
        return dict(data)
    try:
        result = await asyncio.to_thread(search_youtube)
        return result
    except Exception as e:
        return f"Error occurred while searching youtube: {str(e)}"
    

@tool
async def youtube_video_transcript(video_id_: str):
    """Get the transcript of a YouTube video by its youtube video ID."""
    def transcript():
        return f"Cannot provide direct transcript for the video (ID: {video_id_}) as it is protected by copyright and is not accessible as plain text."
    return await asyncio.to_thread(transcript)