import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import jwt  # PyJWT library

app = FastAPI(title="JWT Magic Link SMTP Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── CONFIGURATION ──────────────────────────────────────────────────
SENDER_GMAIL = "gdsc.fan311@gmail.com"  # <-- Your real Gmail address
GMAIL_APP_PASSWORD = "jlmn wosm efrb gxaw"     # <-- Your 16-character App Password

# Keep this secret! This key is used to sign and verify your JWTs.
JWT_SECRET_KEY = "super-secret-random-key-change-this-in-production"
JWT_ALGORITHM = "HS256"
# ────────────────────────────────────────────────────────────────────

class RequestSchema(BaseModel):
    email: EmailStr

# --- ENDPOINT 1: GENERATE JWT AND EMAIL THE LINK ---
@app.post("/v1/auth/otp/request")
async def send_jwt_magic_link(payload: RequestSchema):
    target_destination = payload.email.lower()
    
    # 1. Define what information is hidden inside the token (the payload)
    token_payload = {
        "sub": target_destination,  # Subject (the user's email)
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15), # Expiration time
        "iat": datetime.datetime.now(datetime.timezone.utc) # Issued-at time
    }
    
    # 2. Cryptographically sign and create the JWT string
    generated_jwt = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    # 3. Construct the actual link that points back to our Python server verification route
    magic_link_url = f"http://127.0.0.1:8000/v1/auth/magic-verify?token={generated_jwt}"
    print(f"\n[JWT GENERATED] Link: {magic_link_url}")

    # 4. Build the HTML Email Envelope
    container_envelope = MIMEMultipart()
    container_envelope['From'] = SENDER_GMAIL
    container_envelope['To'] = target_destination
    container_envelope['Subject'] = "✨ Secure Sign-Up Magic Link"
    
    html_markup = f"""
        <div style="font-family: sans-serif; padding: 25px; border: 1px solid #e2e8f0; max-width: 400px; border-radius: 12px; background-color: #ffffff;">
            <h2 style="color: #4f46e5; margin-top: 0;">One-Click Sign Up</h2>
            <p style="color: #334155; font-size: 14px; line-height: 1.5;">Click the secure button below to verify your email identity and finalize your registration sequence:</p>
            
            <div style="text-align: center; margin: 24px 0;">
                <a href="{magic_link_url}" style="background-color: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Log In Instantly</a>
            </div>
            
            <p style="color: #94a3b8; font-size: 11px; margin-bottom: 0;">This link is state-secure and will expire automatically in 15 minutes.</p>
        </div>
    """
    container_envelope.attach(MIMEText(html_markup, 'html'))

    # 5. Connect and broadcast over Google SMTP
    try:
        smtp_connector = smtplib.SMTP("smtp.gmail.com", 587)
        smtp_connector.starttls()  
        smtp_connector.login(SENDER_GMAIL, GMAIL_APP_PASSWORD)
        smtp_connector.sendmail(SENDER_GMAIL, target_destination, container_envelope.as_string())
        smtp_connector.quit()
        
        return {"status": "success", "detail": "Magic link cleanly dispatched."}
    except Exception as smtp_error:
        print(f"[SMTP ERROR] Connection or auth failed: {smtp_error}")
        raise HTTPException(status_code=500, detail="Mail pipeline delivery routing failed.")


# --- ENDPOINT 2: VERIFY JWT CLICK (TRIGGERS WHEN LINK IS CLICKED) ---
@app.get("/v1/auth/magic-verify")
async def verify_jwt_link(token: str = Query(...)):
    try:
        # Decode and verify the token signature and expiration automatically
        decoded_payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_email = decoded_payload["sub"]
        
        # Return a simple successful message or redirect to your app dashboard
        return {
            "status": "success",
            "message": f"🎉 Verification complete! Welcome aboard, {user_email}.",
            "detail": "The JWT signature matches perfectly and hasn't expired."
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="This magic link has expired. Please request a new one.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid, tampered, or broken magic link token.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)