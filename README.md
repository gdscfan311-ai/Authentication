

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



# 2.  OTP Authentication Service

## Overview

This service provides email-based One-Time Password (OTP) authentication using FastAPI and Gmail SMTP. It generates a secure 6-digit OTP, delivers it to the user's email address, and verifies the submitted code before granting access.

---

## Authentication Flow

```text
User Email
    │
    ▼
Request OTP
    │
    ▼
Generate Secure OTP
    │
    ▼
Hash OTP (SHA-256)
    │
    ▼
Store Hash + Expiry + Attempt Counter
    │
    ▼
Send OTP via Email
    │
    ▼
User Submits OTP
    │
    ▼
Hash Submitted OTP
    │
    ▼
Compare Hashes
    │
    ▼
Success / Failure
```

---

## Features

### Secure OTP Generation

* Cryptographically secure 6-digit OTP generation using Python's `secrets` module.
* OTP range: `100000 - 999999`.

### OTP Hashing

* OTPs are hashed using SHA-256 before storage.
* Plaintext OTPs are never stored after generation.
* Verification is performed by hashing the submitted OTP and comparing it against the stored hash.

### OTP Expiration

* OTP validity period: **5 minutes**
* Expired OTPs are automatically rejected.

### Verification Protection

* Maximum verification attempts: **5**
* OTP is invalidated after exceeding the attempt limit.
* Temporary lockout applied after repeated failures.

### Request Rate Limiting

* Maximum OTP requests per email: **3 per hour**
* Resend cooldown: **30 seconds**

### Email Validation

* Email addresses are validated using Pydantic's `EmailStr`.

### One-Time Use

* OTPs are immediately deleted after successful verification.

### Secure Email Transport

* Gmail SMTP with TLS encryption.
* Certificate validation enabled using Python SSL context.

---

## API Endpoints

### Request OTP

`POST /v1/auth/otp/request`

Request:

```json
{
  "email": "user@example.com"
}
```

Response:

```json
{
  "status": "success"
}
```

---

### Verify OTP

`POST /v1/auth/otp/verify`

Request:

```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

Response:

```json
{
  "status": "success"
}
```

---

## Current Security Controls

| Control               | Status |
| --------------------- | ------ |
| Secure OTP Generation | ✅      |
| OTP Hashing           | ✅      |
| OTP Expiration        | ✅      |
| Attempt Limiting      | ✅      |
| Temporary Lockouts    | ✅      |
| Email Validation      | ✅      |
| SMTP TLS Encryption   | ✅      |
| Rate Limiting         | ✅      |
| Resend Cooldown       | ✅      |
| One-Time Use OTP      | ✅      |

---

## Current Limitations

The current implementation is designed for small-scale deployments and proof-of-concept environments.

Known limitations:

* Authentication state is stored in memory.
* Active OTPs are lost if the server restarts.
* No Redis-backed distributed storage.
* No IP-based rate limiting.
* No Web Application Firewall (WAF).
* No session binding mechanism.
* No asynchronous email queue.
* No email delivery tracking.
* Gmail SMTP is used as the mail provider.
* CORS is currently configured with `allow_origins=["*"]`.

---

## Future Enhancements

### Infrastructure

* Redis-based OTP storage
* Redis-backed rate limiting
* Distributed lockout management

### Security

* IP-based rate limiting
* Cloudflare/AWS WAF integration
* Session binding using UUIDs
* Exponential lockout policies

### Email Delivery

* Migration to Amazon SES, SendGrid, or Postmark
* SPF, DKIM, and DMARC configuration
* Delivery status tracking via webhooks

### Scalability

* Background email processing
* Worker queue integration
* Horizontal scaling support




