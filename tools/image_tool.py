import uuid, io, os, aioboto3, asyncio
from typing import Optional
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from postgre.connection import async_pool
from google import genai
from google.genai.types import Part, GenerateContentConfig, ImageConfig
from langgraph.graph import MessagesState
from typing import Optional, Annotated
from langgraph.prebuilt import InjectedState

def get_text(content):
    if isinstance(content, list):
        return "".join(x.get("text", "") for x in content if isinstance(x, dict))
    else:
        return content
    
@tool
async def generate_ai_image(prompt: str, config: RunnableConfig, state: Annotated[MessagesState, InjectedState],  image_path: Optional[str] = None, aspect_ratio: str = '16:9', image_size: str = '2k'):
    """As per user request Generate an AI image with given prompt, image path if asked, aspect ratio if asked, image size if asked as input."""
    user_id = config['configurable']['user_id'] # type: ignore
    model = config['configurable']['model_version'] # type: ignore

    for message in reversed(state["messages"]):
        if getattr(message, "type", None) in {"human", "user"}:
            query = get_text(message.content)
            break

    full_prompt = f"user_query:\n{query} AI_Prompt:\n{prompt}"

    if model != 'jomoai':
        return {
                    "message": "Image cannot be generated with user's selected Model, shift to JomoAI to generate Image or get JomoAI Pro",
                    "filename": ""
                } # type: ignore
    try:
        # 1. API Call (Pehle API call karo)
        response = await generate_image(full_prompt, aspect_ratio, image_size, image_path)
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
        for part in response.candidates[0].content.parts: # type: ignore
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



async def generate_image(prompt: str, aspect_ratio: str, image_size: str, image_path: Optional[str] = None):
    client = genai.Client(vertexai=True, project="project-45267852-1c84-4327-ba7", location="global")
    
    if image_path:
        # 1. Local path se file read karni padegi (Kyuki Vertex from_uri local paths support nahi karta)
        def read_local_file():
            with open(image_path, "rb") as f:
                return f.read()
                
        # asyncio isliye taki main thread block na ho
        image_data = await asyncio.to_thread(read_local_file)

        response = await client.aio.models.generate_content(
            model="gemini-3.1-flash-image",
            contents=[
                prompt,
                Part.from_bytes(
                    data=image_data,
                    mime_type="image/jpeg", # Ya png jo bhi ho
                ),
            ],
            config=GenerateContentConfig(
                response_modalities=['IMAGE', 'TEXT'],
                image_config=ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=image_size
                )
            )
        )
        return response  # <--- Return laga diya taki overwrite na ho

    # Agar image_path nahi hai (Normal Text to Image)
    response = await client.aio.models.generate_content(
        model="gemini-3.1-flash-image",
        contents=prompt,
        config=GenerateContentConfig(
            response_modalities=['IMAGE', 'TEXT'],
            image_config=ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size
            )
        )
    )
    return response