import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from postgre.connection import async_pool
import bcrypt, numpy as np, datetime as dt
from security.templates import get_otp_html

def generate_otp() -> str:
    # FIXED: har baar naya OTP generate hota hai, module-level static value nahi
    return str(np.random.randint(100000, 999999))

def build_email(otp: str) -> tuple[str, str, str]:
    subject = "Your Jomo AI Login OTP"
    content_plain = f"Your OTP is: {otp}. It expires in 5 minutes."
    content_html = get_otp_html(otp)
    return subject, content_plain, content_html

async def create_row(email, otp: str) -> dict:
    hashed = bcrypt.hashpw(otp.encode(), salt=bcrypt.gensalt()).decode() 
    async with async_pool.connection() as conn:
        await conn.execute(
            "INSERT INTO otp_validation (email, expiry_time, encrypted_otp, attempt_count) VALUES (%s, %s, %s, 0)",
            (email, dt.datetime.now() + dt.timedelta(minutes=5), hashed),
        )
        await conn.commit()
    return {'message': f"Otp generated and sent to {email}"}

async def update_row(email):
    async with async_pool.connection() as conn:
        await conn.execute(
            "UPDATE otp_validation SET attempt_count = attempt_count + 1 WHERE email = %s",
            (email,),
        )
        await conn.commit()  # FIXED: commit missing tha pehle

async def delete_row(email):
    async with async_pool.connection() as conn:
        await conn.execute(
            "DELETE FROM otp_validation WHERE email = %s",
            (email,),
        )
        await conn.commit()  # FIXED: commit missing tha pehle

async def otp_status(email_id):
    async with async_pool.connection() as conn:
        cur = await conn.execute(
            "SELECT status, expiry_time FROM otp_validation WHERE email = %s",
            (email_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return False
        if dt.datetime.now() >= row['expiry_time']:
            return False
        return row['status']

async def time_remaining(email_id):
    async with async_pool.connection() as conn:
            cur = await conn.execute(
                "SELECT expiry_time FROM otp_validation WHERE email = %s",
                (email_id,),
            )
            row = await cur.fetchone()
            if not row:
                  return False
            return dt.datetime.now() < row['expiry_time']




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

async def send_email_async(recipient_email: str, subject: str, content: str, html_content: str = None):
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
            req = gmail.users.messages.send(
                userId="me",
                json={'raw': encoded_message}
            )
            response = await aiogoogle.as_user(req)
            return response
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Email server error: {str(error)}")
