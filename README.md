

# 1. Token-Based Backend


* **Core Technology:** This backend uses JWT magic link authentication. It does not generate a numeric OTP. Instead, it creates a signed token and sends that token inside a clickable email link.

### Main Purpose

User enters email -> backend creates JWT -> sends magic link -> user clicks link -> backend verifies JWT

### App Initialization & CORS Configuration

* The app is created with:
```python
app = FastAPI(title="JWT Magic Link SMTP Server")

```


* It allows frontend requests using CORS:
```python
allow_origins=["*"]

```


* *Note:* This means any frontend origin can call the backend. It is okay for testing, but not secure for production.



### Hardcoded Configuration Values

The backend has these hardcoded configuration values:

* `SENDER_GMAIL`: The Gmail account used to send emails.
* `GMAIL_APP_PASSWORD`: The Gmail app password used for SMTP login.
* `JWT_SECRET_KEY`: Signs and verifies the JWT token.
* `JWT_ALGORITHM = "HS256"`: Means it uses HMAC SHA-256 signing.

### Request Schema

```python
class RequestSchema(BaseModel):
    email: EmailStr

```

* *Note:* This means the API expects a valid email in the request body.

### Main Endpoints

* `POST /v1/auth/otp/request`
* `GET  /v1/auth/magic-verify`

### Endpoint 1: Request Processing Details

```python
@app.post("/v1/auth/otp/request")
async def send_jwt_magic_link(payload: RequestSchema):

```

* Even though the route says otp, it actually creates a JWT token.
* Inside this endpoint, the email is normalized:
```python
target_destination = payload.email.lower()

```


* Then the JWT payload is created:
```python
token_payload = {
    "sub": target_destination,
    "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15),
    "iat": datetime.datetime.now(datetime.timezone.utc)
}

```


* `sub` = user email
* `exp` = token expires after 15 minutes
* `iat` = token creation time


* Then the JWT is generated:
```python
generated_jwt = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

```


* *Note:* This creates a long signed token. The user cannot safely modify it because the signature would fail during verification.


* Then it builds a magic link:
```python
magic_link_url = f"http://127.0.0.1:8000/v1/auth/magic-verify?token={generated_jwt}"

```


* **Important issue:** this link uses port 8000, but the backend at the bottom runs on port 5500:
```python
uvicorn.run("main:app", host="127.0.0.1", port=5500, reload=True)

```


So either the link should use 5500, or the server should run on 8000.


* The backend builds an HTML email using:
```python
MIMEMultipart()
MIMEText(html_markup, 'html')

```


* Then it sends the email using Gmail SMTP:
```python
smtp_connector = smtplib.SMTP("smtp.gmail.com", 587)
smtp_connector.starttls()
smtp_connector.login(SENDER_GMAIL, GMAIL_APP_PASSWORD)
smtp_connector.sendmail(...)
smtp_connector.quit()

```



### Endpoint 2: Verification Details

```python
@app.get("/v1/auth/magic-verify")
async def verify_jwt_link(token: str = Query(...)):

```

* It receives the token from the URL query parameter: `/v1/auth/magic-verify?token=...`
* Then it verifies the token:
```python
decoded_payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

```


* If valid, it extracts the email:
```python
user_email = decoded_payload["sub"]

```


* If the token has expired, it raises: `jwt.ExpiredSignatureError`
* If the token is invalid or changed, it raises: `jwt.InvalidTokenError`

### Security Features in Token Backend

* JWT is signed
* JWT expires in 15 minutes
* Email is stored inside token as subject
* Token cannot be modified without invalidating signature
* SMTP connection uses TLS
* Email input is validated

### Security Weaknesses

* Gmail app password is hardcoded
* JWT secret is hardcoded and weak
* CORS allows all origins
* No database user/session creation after verification
* Magic link port does not match server port
* No rate limiting
* No protection against repeated email requests







2. OTP-Based Backend

Core Technology

This backend uses a secure 6-digit email OTP authentication system built with FastAPI.

Main Purpose

User enters email → backend generates secure OTP → OTP is hashed and stored → OTP is sent by email → user enters OTP → backend verifies the submitted code against the stored hash.

App Initialization & CORS Configuration

The application is initialized using FastAPI.

Cross-Origin Resource Sharing (CORS) is enabled to allow frontend applications to communicate with the authentication API.

Current Configuration

allow_origins=["*"]

Note:

This configuration is acceptable for development and testing environments but should be restricted to trusted frontend domains in production deployments.

Configuration Values

The application loads the following configuration values:

• SENDER_GMAIL
• GMAIL_APP_PASSWORD

These credentials are used to authenticate with Gmail SMTP for transactional email delivery.

Data Storage

The backend currently stores authentication state in memory using Python dictionaries:

• otp_store
• otp_send_history
• otp_verify_lockouts

OTP records contain:

• Hashed OTP value
• Expiration timestamp
• Verification attempt counter

Example:

{
"[user@example.com](mailto:user@example.com)": {
"code_hash": "...",
"expires_at": 1234567890,
"attempts": 0
}
}

Note:

The plaintext OTP is never stored after generation. Only its cryptographic hash is retained.

Request and Verification Schemas

OTP Request Schema

class RequestSchema(BaseModel):
email: EmailStr

Purpose:

Used when requesting a new OTP.

OTP Verification Schema

class VerifySchema(BaseModel):
email: EmailStr
code: str

Purpose:

Used when verifying a submitted OTP.

Main Endpoints

POST /v1/auth/otp/request

POST /v1/auth/otp/verify

Endpoint 1: OTP Request Processing

The endpoint receives a valid email address.

The submitted email is normalized to lowercase to ensure consistency.

Before generating an OTP, the system performs several security checks:

• Verification lockout status
• OTP resend cooldown period
• Email-based rate limiting

Current Controls

• Maximum 3 OTP requests per hour per email address
• 30-second cooldown between OTP requests
• Temporary lockout enforcement

OTP Generation

The system generates a cryptographically secure 6-digit OTP using a secure random source.

Examples:

193847
650291
904422

OTP Protection

Immediately after generation, the OTP is hashed using SHA-256.

Only the hash is stored in memory.

The plaintext OTP is sent to the user via email and is not retained for verification purposes.

OTP Expiration

Each OTP is assigned a five-minute validity period.

Expired OTPs are automatically rejected during verification.

Email Delivery

The OTP is inserted into the HTML email body and delivered through Gmail SMTP.

Transport Security

SMTP communication is protected using TLS with certificate validation enabled.

Endpoint 2: OTP Verification Processing

The endpoint receives:

{
"email": "[user@example.com](mailto:user@example.com)",
"code": "482913"
}

The verification workflow performs the following checks:

1. Verify that the account is not currently locked.
2. Verify that an active OTP exists.
3. Verify that the OTP has not expired.
4. Hash the submitted OTP using SHA-256.
5. Compare the generated hash with the stored hash.

Successful Verification

If the hashes match:

• Authentication succeeds.
• The OTP record is immediately deleted.
• The OTP becomes unusable for future requests.

Failed Verification

If the hashes do not match:

• The verification attempt counter is incremented.
• The user receives an authentication failure response.

Account Lockout Protection

The system tracks failed verification attempts.

Maximum Failed Attempts:

5

If the limit is exceeded:

• The OTP is invalidated.
• A temporary lockout is applied.
• Additional verification attempts are blocked until the lockout expires.

Current Lockout Duration:

5 minutes

Security Features

• Cryptographically secure OTP generation
• SHA-256 OTP hashing
• TLS-secured email transport
• Email format validation
• OTP expiration (5 minutes)
• One-time-use OTPs
• Verification attempt tracking
• Temporary account lockouts
• Email-based rate limiting
• OTP resend cooldown controls

Current Security Limitations

• Authentication state is stored in memory only
• Server restarts invalidate all active OTPs
• No distributed storage for horizontal scaling
• No IP-based rate limiting
• No Web Application Firewall (WAF)
• No session binding mechanism
• No background email queue
• No delivery tracking or observability
• Gmail SMTP remains the email transport provider
• CORS configuration is overly permissive for production environments
• OTP values are currently logged during generation and should be removed before production deployment

Current Security Assessment

Overall Security Score: 8.0/10

The system provides strong protection against common OTP attacks through secure token generation, cryptographic hashing, expiration controls, lockout mechanisms, and rate limiting. Remaining improvements are primarily focused on scalability, operational resilience, abuse prevention, and enterprise-grade infrastructure.
in memory
* Server restart deletes all OTP
