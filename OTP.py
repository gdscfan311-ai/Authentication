import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

app = FastAPI(title="Global Target SMTP Server")

# Handle CORS allowances so you can open files locally directly via browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── CONFIGURATION (INSERT YOUR AUTH PROFILE) ───────────────────────
SENDER_GMAIL = "gdsc.fan311@gmail.com"  # <-- YOUR REAL GMAIL HERE
GMAIL_APP_PASSWORD = "jlmn wosm efrb gxaw"     # <-- YOUR 16-CHAR APP PASSWORD
# ────────────────────────────────────────────────────────────────────

# Runtime active token cache dictionary
otp_store = {}

class RequestSchema(BaseModel):
    email: EmailStr

class VerifySchema(BaseModel):
    email: EmailStr
    code: str

@app.post("/v1/auth/otp/request")
async def send_global_otp(payload: RequestSchema):
    target_destination = payload.email.lower()
    
    # 1. Spin up a random numeric combination
    generated_otp = f"{random.randint(100000, 999999)}"
    otp_store[target_destination] = generated_otp
    print(f"\n[SMTP DISPATCH] Generated Code {generated_otp} heading out to -> {target_destination}")

    # 2. Structure transactional structural email headers
    container_envelope = MIMEMultipart()
    container_envelope['From'] = SENDER_GMAIL
    container_envelope['To'] = target_destination
    container_envelope['Subject'] = f"[ALRT-{generated_otp}] Outbound Localhost Security Verification Verification Link Token"
    
    html_markup = f"""
        <div style="font-family: monospace; padding: 25px; border: 2px dashed #4f46e5; max-width: 450px; background-color: #fafafa;">
            <h3 style="color: #4f46e5; margin-top: 0;">⚡ TRANSACTIONAL DISPATCH ROUTER</h3>
            <p style="color: #334155; font-size: 13px;">A remote connection request from a local backend development loop has requested authentication validation.</p>
            <div style="background: #1e293b; padding: 20px; text-align: center; font-size: 36px; font-weight: bold; letter-spacing: 6px; color: #38bdf8; margin: 20px 0; border-radius: 4px;">
                {generated_otp}
            </div>
            <p style="color: #64748b; font-size: 11px; border-top: 1px solid #e2e8f0; padding-top: 10px; margin-bottom: 0;">Origin Relay IP Node: 127.0.0.1 (Localhost Engine)</p>
        </div>
    """
    container_envelope.attach(MIMEText(html_markup, 'html'))

    # 3. Establish structural SMTP relay loops
    try:
        smtp_connector = smtplib.SMTP("smtp.gmail.com", 587)
        smtp_connector.starttls()  # Encrypt channel
        smtp_connector.login(SENDER_GMAIL, GMAIL_APP_PASSWORD)
        
        # Fire transmission
        smtp_connector.sendmail(SENDER_GMAIL, target_destination, container_envelope.as_string())
        smtp_connector.quit()
        
        return {"status": "success", "detail": "Email routing passed cleanly over live relay lines."}
    except Exception as network_error:
        print(f"[REJECTED SYSTEM ERROR] Google SMTP closed link channels: {network_error}")
        raise HTTPException(status_code=500, detail="Mail pipeline failed. Double-check your Google App Password configuration entries.")

@app.post("/v1/auth/otp/verify")
async def check_global_otp(payload: VerifySchema):
    target_destination = payload.email.lower()
    user_token = payload.code

    if target_destination not in otp_store:
        raise HTTPException(status_code=400, detail="No pending active codes maps out to that target address.")

    if otp_store[target_destination] == user_token:
        del otp_store[target_destination]
        return {"status": "success", "detail": "Token matched successfully. Authorized."}
    else:
        raise HTTPException(status_code=400, detail="Mismatched token submission value.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)