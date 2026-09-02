import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from security.templates import get_otp_html

def generate_otp() -> str:
    # FIXED: har baar naya OTP generate hota hai, module-level static value nahi
    return str(np.random.randint(100000, 999999))

def build_email(otp: str) -> tuple[str, str, str]:
    subject = "Your Jomo AI Login OTP"
    content_plain = f"Your OTP is: {otp}. It expires in 5 minutes."
    content_html = get_otp_html(otp)
    return subject, content_plain, content_html

import os, base64
from email.message import EmailMessage
from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import ClientCreds, UserCreds
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

OTP_CLIENT_ID = os.getenv("OTP_CLIENT_ID")
OTP_CLIENT_SECRET = os.getenv("OTP_CLIENT_SECRET")
OTP_REFRESH_TOKEN = os.getenv("OTP_REFRESH_TOKEN")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "noreply.jomoai@gmail.com")

if OTP_CLIENT_ID and OTP_CLIENT_SECRET and OTP_REFRESH_TOKEN:
    client_creds = ClientCreds(client_id=OTP_CLIENT_ID, client_secret=OTP_CLIENT_SECRET)
    user_creds = UserCreds(refresh_token=OTP_REFRESH_TOKEN)
else:
    client_creds = None
    user_creds = None

async def send_email_async(recipient_email: str, subject: str, content: str, html_content: str = None): # type: ignore
    if not client_creds:
        raise HTTPException(status_code=500, detail="OAuth credentials for email not configured properly.")
        
    message = EmailMessage()
    message.set_content(content)
    message['To'] = recipient_email
    message['From'] = SENDER_EMAIL
    message['Subject'] = subject
    if html_content:
        message.add_alternative(html_content, subtype='html')
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    try:
        async with Aiogoogle(client_creds=client_creds, user_creds=user_creds) as aiogoogle:
            gmail = await aiogoogle.discover('gmail', 'v1')
            req = gmail.users.messages.send(userId="me", json={'raw': encoded_message}) # type: ignore
            response = await aiogoogle.as_user(req)
            return response
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Email server error: {str(error)}")


#=================================================================
#======================== OTP Authentication =====================
import bcrypt
import numpy as np
from pydantic import BaseModel, EmailStr
from fastapi import HTTPException, APIRouter
from security.redis_connection import async_redis

from backend.user.user import email_exists 

class EmailFormat(BaseModel):
    id: EmailStr

router = APIRouter()

@router.post("/send_otp")
async def Send_Email(email: EmailFormat) -> dict:
    if await email_exists(email.id): 
        return {"status": "Email already exists"}
        
    if await async_redis.get(f"{email.id}timer"):
        return {"status": "Please try after some time."}
        
    otp = generate_otp()
    hashed = bcrypt.hashpw(otp.encode(), salt=bcrypt.gensalt()).decode()
    
    try:
        await async_redis.set(email.id, hashed, ex=300)
        await async_redis.set(f"{email.id}timer", "locked", ex=120) # 120 seconds cooldown timer
    except Exception as e:
        return {'status': f"otp cannot be updated, error: {str(e)}"}
    
    subject, content, html_content = build_email(otp)
    try:
        await send_email_async(recipient_email=email.id, subject=subject, content=content, html_content=html_content)
    except Exception as e:
        return {'status': f"can not authenticate with email otp right now, error: {str(e)}"}

    return {
        'status': f"Otp sent to your Email {email.id}, otp valid for 5 minutes", 
    }


@router.post("/send_otp_to_registered_user")
async def Send_Email_to_registered_user(email: EmailFormat) -> dict:
    if not await email_exists(email.id): 
        return {"status": "Email not exists"}
        
    if await async_redis.get(f"{email.id}timer"):
        return {"status": "Please try after some time."}
    
    otp = generate_otp()
    hashed = bcrypt.hashpw(otp.encode(), salt=bcrypt.gensalt()).decode()
    
    try:
        await async_redis.set(email.id, hashed, ex=300)
        await async_redis.set(f"{email.id}timer", "locked", ex=120) # 120 seconds cooldown timer
    except Exception as e:
        return {'status': f"otp cannot be updated, error: {str(e)}"}

    subject, content, html_content = build_email(otp)
    try:
         await send_email_async(recipient_email=email.id, subject=subject, content=content, html_content=html_content)
    except Exception as e:
         return {'status': f"can not authenticate with email otp right now, error: {str(e)}"}
    
    return {
         'status': f"Otp sent to your Email {email.id}, otp valid for 5 minutes", 
     }


class EmailFormat1(BaseModel):
    id: EmailStr
    otp: str

@router.post("/verify_otp")
async def verify_otp(user: EmailFormat1):
    fetched_otp = await async_redis.get(user.id)
    
    if not fetched_otp:
        return {'error': 'Session Expired or Wrong Otp'}
    
    attempts = await async_redis.incr(f"attempt{user.id}")

    if attempts == 1:
        await async_redis.expire(f"attempt{user.id}", 300)

    if attempts > 3:
        await async_redis.delete(user.id)
        await async_redis.delete(f"attempt{user.id}")
        return {'error': 'Too many failed attempts. Please try again later.'}

    if not bcrypt.checkpw(user.otp.encode(), fetched_otp.encode()): # type: ignore
        return {'error': f'Invalid Otp more {3 - attempts} attempts left'}

    # Success hone par otp aur attempts RAM se turant saaf kar diye
    await async_redis.delete(user.id)
    await async_redis.delete(f"attempt{user.id}")
    
    # Status verified mark kar diya
    await async_redis.set(f"{user.id}status", "verified", ex=360)
    
    return True


async def otp_status(email_id):
    status = await async_redis.get(f"{email_id}status")
    
    if status is None:
        return False
    if status == "verified":
        return True
    
    return False # Baaki saari situations (jaise "pending") me False return karega
