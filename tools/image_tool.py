import uuid, io, os, aioboto3
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from postgre.connection import async_pool
from google import genai

@tool
async def generate_ai_image(prompt: str, config: RunnableConfig) -> str:
    """As per user request Generate an AI image with giving prompt as input."""
    user_id = config['configurable']['user_id']
    try:
        # 1. API Call (Pehle API call karo)
        client = genai.Client(vertexai=True, project="project-45267852-1c84-4327-ba7", location="global")
        response = await client.aio.models.generate_content(model="gemini-3.1-flash-image",contents=prompt,)

        # ======================================================================
        # 2. REAL TOKENS COUNTS
        real_tokens = 24000
            
        # 3. UPDATE DB WITH REAL TOKENS ONLY
        async with async_pool.connection() as conn:
            await conn.execute("""
                INSERT INTO daily_usage (user_id, tokens, date)
                VALUES (%s, %s, CURRENT_DATE)
                ON CONFLICT (user_id, date)
                DO UPDATE SET tokens = daily_usage.tokens + EXCLUDED.tokens
            """, (user_id, real_tokens))
            await conn.commit()
        # ======================================================================

        image_bytes = None
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                break
                
        if not image_bytes:
            return "System Error: Model did not return an image."

        # 4. Upload to S3 (Tera aioboto3 logic)
        unique_filename = f"ai_gen_{uuid.uuid4().hex[:8]}.png"
        key = f"upload/{user_id}/{unique_filename}"
        
        session = aioboto3.Session()
        async with session.client(
            service_name="s3",
            endpoint_url=os.getenv("ENDPOINT_URL"),
            aws_access_key_id=os.getenv("ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("SECRET_ACCESS_KEY"),
            region_name="auto",
        ) as s3_client: # type: ignore
            file_obj = io.BytesIO(image_bytes)
            await s3_client.upload_fileobj(file_obj, Bucket=os.getenv("BUCKET_NAME"), Key=key)
        
        return {
            "message": "Image successfully generated and saved to your files!",
            "filename": unique_filename
        } # type: ignore
        
    except Exception as e:
        return f"Failed to generate image due to technical error: {str(e)}"
