

# 1. Token-Based Backend

* **File Path:** `C:\Users\abhyu\OneDrive\Desktop\Test\Tokenbased\main.py`
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








# 2. OTP-Based Backend

* **File Path:** `C:\Users\abhyu\OneDrive\Desktop\Test\OTP\OTP.py`
* **Core Technology:** This backend uses a classic 6-digit email OTP system.

### Main Purpose

User enters email -> backend generates 6-digit OTP -> sends OTP by email -> user enters OTP -> backend verifies it

### App Initialization & CORS Configuration

* The app is created with:
```python
app = FastAPI(title="Global Target SMTP Server")

```


* It also enables CORS:
```python
allow_origins=["*"]

```


* *Note:* Again, okay for local testing, but too open for production.



### Configuration Values

* `SENDER_GMAIL`
* `GMAIL_APP_PASSWORD`
* These are used to log into Gmail SMTP and send the OTP email.



### Data Storage

* The backend stores OTPs in memory:
```python
otp_store = {}

```


* Example after generating an OTP:
```json
{
    "user@example.com": "482913"
}

```



### Request and Verification Schemas

```python
class RequestSchema(BaseModel):
    email: EmailStr

```

* *Note:* This is used when requesting an OTP.

```python
class VerifySchema(BaseModel):
    email: EmailStr
    code: str

```

* *Note:* This is used when verifying the OTP.

### Main Endpoints

* `POST /v1/auth/otp/request`
* `POST /v1/auth/otp/verify`

### Endpoint 1: Request Processing Details

```python
@app.post("/v1/auth/otp/request")
async def send_global_otp(payload: RequestSchema):

```

* It takes the submitted email:
```python
target_destination = payload.email.lower()

```


* Then generates the OTP:
```python
generated_otp = f"{random.randint(100000, 999999)}"

```


* *Note:* This creates a random 6-digit number from 100000 to 999999. Examples: 193847, 650291, 904422.


* Then it stores the OTP:
```python
otp_store[target_destination] = generated_otp

```


* *Note:* So each email has its own OTP.


* Then it builds an HTML email and inserts the OTP into the email body: `{generated_otp}`
* It also puts the OTP in the email subject:
```python
container_envelope['Subject'] = f"[ALRT-{generated_otp}] ..."

```


* *Note:* That works, but it is not ideal for privacy because email subjects are often more visible.


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
@app.post("/v1/auth/otp/verify")
async def check_global_otp(payload: VerifySchema):

```

* It receives:
```json
{
  "email": "user@example.com",
  "code": "482913"
}

```


* Then it checks whether that email has a pending OTP:
```python
if target_destination not in otp_store:

```


* *Note:* If no OTP exists, it returns an error.


* If an OTP exists, it compares:
```python
if otp_store[target_destination] == user_token:

```


* If the code matches, it deletes the OTP:
```python
del otp_store[target_destination]

```


* *Note:* That makes the OTP one-time use.



### Security Features in OTP Backend

* Generates random 6-digit OTP
* OTP is linked to a specific email
* OTP is deleted after successful verification
* Email format is validated
* SMTP uses TLS

### Security Weaknesses

* OTP does not expire
* No wrong-attempt limit
* No resend limit
* Uses random instead of secrets
* Gmail app password is hardcoded
* OTP is visible in email subject
* CORS allows all origins
* OTP is stored only in memory
* Server restart deletes all OTP
