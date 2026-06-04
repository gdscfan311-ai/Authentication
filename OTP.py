        import os
        import hashlib
        import secrets
        import smtplib
        import ssl
        import time
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel, EmailStr


        def load_env_file(env_path: str = ".env") -> None:
            if not os.path.exists(env_path):
                return

            with open(env_path, "r", encoding="utf-8") as env_file:
                for raw_line in env_file:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")

                    if key and key not in os.environ:
                        os.environ[key] = value


        load_env_file()

        app = FastAPI(title="Global Target SMTP Server")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        SENDER_GMAIL = os.getenv("SENDER_GMAIL")
        GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

        otp_store = {}
        otp_send_history = {}
        otp_verify_lockouts = {}
        OTP_TTL_SECONDS = 5 * 60
        OTP_RATE_LIMIT_COUNT = 3
        OTP_RATE_LIMIT_WINDOW_SECONDS = 60 * 60
        OTP_MAX_VERIFY_ATTEMPTS = 5
        OTP_VERIFY_LOCKOUT_SECONDS = OTP_TTL_SECONDS
        OTP_RESEND_COOLDOWN_SECONDS = 30


        class RequestSchema(BaseModel):
            email: EmailStr


        class VerifySchema(BaseModel):
            email: EmailStr
            code: str


        def prune_old_send_attempts(target_destination: str, current_time: float) -> int:
            send_attempts = otp_send_history.get(target_destination, [])
            fresh_attempts = [
                attempt_time
                for attempt_time in send_attempts
                if current_time - attempt_time < OTP_RATE_LIMIT_WINDOW_SECONDS
            ]
            otp_send_history[target_destination] = fresh_attempts
            return len(fresh_attempts)


        def get_resend_reset_at(target_destination: str) -> float | None:
            send_attempts = otp_send_history.get(target_destination, [])
            if len(send_attempts) < OTP_RATE_LIMIT_COUNT:
                return None

            return send_attempts[0] + OTP_RATE_LIMIT_WINDOW_SECONDS


        def get_resend_available_at(target_destination: str) -> float | None:
            send_attempts = otp_send_history.get(target_destination, [])
            if not send_attempts:
                return None

            return send_attempts[-1] + OTP_RESEND_COOLDOWN_SECONDS


        def clear_expired_verify_lockout(target_destination: str, current_time: float) -> None:
            lockout_until = otp_verify_lockouts.get(target_destination)
            if lockout_until is not None and current_time >= lockout_until:
                del otp_verify_lockouts[target_destination]


        @app.post("/v1/auth/otp/request")
        async def send_global_otp(payload: RequestSchema):
            if not SENDER_GMAIL or not GMAIL_APP_PASSWORD:
                raise HTTPException(
                    status_code=500,
                    detail="Mail pipeline is not configured. Set SENDER_GMAIL and GMAIL_APP_PASSWORD.",
                )

            target_destination = payload.email.lower()
            current_time = time.time()
            clear_expired_verify_lockout(target_destination, current_time)

            lockout_until = otp_verify_lockouts.get(target_destination)
            if lockout_until is not None:
                raise HTTPException(
                    status_code=429,
                    detail="Too many incorrect OTP attempts. Please wait before requesting another code.",
                    headers={
                        "Retry-After": str(max(1, int(lockout_until - current_time))),
                    },
                )

            send_count = prune_old_send_attempts(target_destination, current_time)

            resend_available_at = get_resend_available_at(target_destination)
            if resend_available_at is not None and current_time < resend_available_at:
                raise HTTPException(
                    status_code=429,
                    detail="Please wait before resending your code.",
                    headers={"Retry-After": str(max(1, int(resend_available_at - current_time)))},
                )

            if send_count >= OTP_RATE_LIMIT_COUNT:
                reset_at = get_resend_reset_at(target_destination)
                raise HTTPException(
                    status_code=429,
                    detail="OTP request limit reached. Please wait before requesting another code.",
                    headers={"Retry-After": str(max(1, int((reset_at or current_time) - current_time)))},
                )

            generated_otp = str(secrets.randbelow(900000) + 100000)
            otp_hash = hashlib.sha256(generated_otp.encode()).hexdigest()
            otp_store[target_destination] = {
                "code_hash": otp_hash,
                "expires_at": current_time + OTP_TTL_SECONDS,
                "attempts": 0,
            }
            otp_send_history[target_destination].append(current_time)
            print(f"\n[SMTP DISPATCH] Generated Code {generated_otp} heading out to -> {target_destination}")

            container_envelope = MIMEMultipart()
            container_envelope["From"] = SENDER_GMAIL
            container_envelope["To"] = target_destination
            container_envelope["Subject"] = "Cyveon Verification Code"

            html_markup = f"""
                <div style="margin:0; padding:24px; background:#f5f7fa;">
                    <div style="max-width:640px; margin:0 auto; background:#ffffff; border:1px solid #d9e1ea; border-radius:18px; overflow:hidden; font-family:Arial,Helvetica,sans-serif; color:#0f172a; box-shadow:0 10px 30px rgba(0,32,64,0.08);">
                        <div style="background:linear-gradient(180deg, #002040 0%, #0f3553 100%); padding:44px 56px;">
                            <div style="font-size:42px; line-height:1.1; font-weight:400; color:#ffffff; letter-spacing:-0.02em;">Cyveon Verification Code</div>
                            <div style="margin-top:16px; width:86px; height:4px; background:#d00000; border-radius:999px;"></div>
                        </div>
                        <div style="padding:44px 56px 36px; background:#ffffff;">
                            <p style="margin:0 0 24px; font-size:20px; line-height:1.45;">Dear "Product Name" user,</p>
                            <p style="margin:0 0 32px; font-size:20px; line-height:1.45;">
                                We received a request to access your "Product Name" account through your email address. Your verification code is:
                            </p>
                            <div style="text-align:center; font-size:54px; line-height:1; font-weight:700; letter-spacing:0.08em; color:#002040; margin:18px 0 34px; padding:18px 12px; border:2px solid #d9e1ea; border-radius:16px; background:#f8fbff;">
                                {generated_otp}
                            </div>
                            <p style="margin:0 0 32px; font-size:18px; line-height:1.5;">
                                If you did not request this code, it is possible that someone else is trying to access your "Product Name" account.
                                <strong style="color:#d00000;">Do not forward or give this code to anyone.</strong>
                            </p>
                            <p style="margin:0; font-size:18px; line-height:1.5;">Sincerely yours,</p>
                            <p style="margin:18px 0 0; font-size:18px; line-height:1.5;">The Cyveon team</p>
                        </div>
                    </div>
                </div>
            """
            container_envelope.attach(MIMEText(html_markup, "html"))

            try:
                smtp_connector = smtplib.SMTP("smtp.gmail.com", 587)
                context = ssl.create_default_context()
                smtp_connector.starttls(context=context)
                smtp_connector.login(SENDER_GMAIL, GMAIL_APP_PASSWORD)
                smtp_connector.sendmail(SENDER_GMAIL, target_destination, container_envelope.as_string())
                smtp_connector.quit()

                remaining_resends = max(0, OTP_RATE_LIMIT_COUNT - send_count - 1)
                return {
                    "status": "success",
                    "detail": "Email routing passed cleanly over live relay lines.",
                    "remaining_resends": remaining_resends,
                    "resend_reset_at": get_resend_reset_at(target_destination),
                    "resend_available_at": current_time + OTP_RESEND_COOLDOWN_SECONDS,
                    "expires_at": otp_store[target_destination]["expires_at"],
                }
            except Exception as network_error:
                print(f"[REJECTED SYSTEM ERROR] Google SMTP closed link channels: {network_error}")
                raise HTTPException(
                    status_code=500,
                    detail="Mail pipeline failed. Double-check your Google App Password configuration entries.",
                )


        @app.post("/v1/auth/otp/verify")
        async def check_global_otp(payload: VerifySchema):
            target_destination = payload.email.lower()
            user_token = payload.code
            current_time = time.time()

            clear_expired_verify_lockout(target_destination, current_time)

            lockout_until = otp_verify_lockouts.get(target_destination)
            if lockout_until is not None:
                raise HTTPException(
                    status_code=429,
                    detail="Too many incorrect OTP attempts. Please wait before trying again.",
                    headers={
                        "Retry-After": str(max(1, int(lockout_until - current_time))),
                    },
                )

            if target_destination not in otp_store:
                raise HTTPException(status_code=400, detail="No pending active codes maps out to that target address.")

            stored_otp = otp_store[target_destination]

            if time.time() > stored_otp["expires_at"]:
                del otp_store[target_destination]
                raise HTTPException(status_code=400, detail="OTP has expired. Please request a new code.")

            user_token_hash = hashlib.sha256(user_token.encode()).hexdigest()

            if stored_otp["code_hash"] == user_token_hash:
                del otp_store[target_destination]
                return {"status": "success", "detail": "Token matched successfully. Authorized."}

            stored_otp["attempts"] += 1

            if stored_otp["attempts"] >= OTP_MAX_VERIFY_ATTEMPTS:
                del otp_store[target_destination]
                otp_verify_lockouts[target_destination] = current_time + OTP_VERIFY_LOCKOUT_SECONDS
                raise HTTPException(
                    status_code=429,
                    detail="Too many incorrect OTP attempts. Please request a new code.",
                    headers={
                        "Retry-After": str(OTP_VERIFY_LOCKOUT_SECONDS),
                    },
                )

            raise HTTPException(status_code=400, detail="Mismatched token submission value.")


        if __name__ == "__main__":
            import uvicorn

            uvicorn.run("OTP:app", host="127.0.0.1", port=8000, reload=True)
