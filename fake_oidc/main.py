"""Small test-only OpenID Connect provider for local and automated journeys."""

from __future__ import annotations

import base64
import csv
import hashlib
import html
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse


app = FastAPI(title="Volunteer CRM Fake OIDC", docs_url=None, redoc_url=None)
ISSUER = os.environ.get("FAKE_OIDC_ISSUER", "http://localhost:9000")
BROWSER_BASE_URL = os.environ.get("FAKE_OIDC_BROWSER_BASE_URL", ISSUER)
INTERNAL_BASE_URL = os.environ.get("FAKE_OIDC_INTERNAL_BASE_URL", "http://fake-oidc:9000")
CLIENT_ID = os.environ.get("FAKE_OIDC_CLIENT_ID", "volunteer-crm")
CLIENT_SECRET = os.environ.get("FAKE_OIDC_CLIENT_SECRET", "fake-oidc-development-secret")
KEY_ID = "fake-oidc-key"
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str
    name: str
    email_verified: bool = True


def seeded_identities() -> list[Identity]:
    seed_path = Path(os.environ.get("FAKE_OIDC_CONTACTS_CSV", "/seed/contacts.csv"))
    if not seed_path.is_file():
        return []
    with seed_path.open(encoding="utf-8") as seed_file:
        return [
            Identity(
                row["id"],
                row["email"],
                f'{row["first_name"]} {row["last_name"]}',
            )
            for row in csv.DictReader(seed_file)
            if row["email"]
        ]


IDENTITIES = {
    identity.subject: identity
    for identity in seeded_identities()
}
AUTHORIZATION_CODES: dict[str, dict[str, str]] = {}


def b64uint(value: int) -> str:
    size = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(size, "big")).rstrip(b"=").decode()


@app.get("/.well-known/openid-configuration")
def discovery() -> dict[str, object]:
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{BROWSER_BASE_URL}/authorize",
        "token_endpoint": f"{INTERNAL_BASE_URL}/token",
        "jwks_uri": f"{INTERNAL_BASE_URL}/jwks",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "email", "profile"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
    }


@app.get("/jwks")
def jwks() -> dict[str, list[dict[str, str]]]:
    numbers = PRIVATE_KEY.public_key().public_numbers()
    return {
        "keys": [{"kty": "RSA", "kid": KEY_ID, "use": "sig", "alg": "RS256", "n": b64uint(numbers.n), "e": b64uint(numbers.e)}]
    }


@app.get("/authorize", response_class=HTMLResponse, response_model=None)
def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str,
    scope: str,
    state: str,
    nonce: str,
    code_challenge: str,
    code_challenge_method: str,
    login_hint: str | None = Query(default=None),
) -> HTMLResponse | RedirectResponse:
    if client_id != CLIENT_ID or response_type != "code" or code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail="Invalid authorization request")
    parameters = {"client_id": client_id, "redirect_uri": redirect_uri, "state": state, "nonce": nonce, "code_challenge": code_challenge}
    if login_hint and login_hint in IDENTITIES:
        return issue_code(login_hint, **parameters)
    buttons = "".join(
        f'<button name="subject" value="{html.escape(item.subject)}">{html.escape(item.name)} — {html.escape(item.email)}</button><br>'
        for item in IDENTITIES.values()
    )
    hidden = "".join(
        f'<input type="hidden" name="{name}" value="{html.escape(value)}">'
        for name, value in parameters.items()
    )
    return HTMLResponse(f"<h1>Fake OIDC sign-in</h1><p>Development and test use only.</p><form method='post' action='/authorize'>{hidden}{buttons}</form>")


@app.post("/authorize")
def authorize_choice(
    subject: str = Form(), client_id: str = Form(), redirect_uri: str = Form(),
    state: str = Form(), nonce: str = Form(), code_challenge: str = Form(),
) -> RedirectResponse:
    return issue_code(subject, client_id, redirect_uri, state, nonce, code_challenge)


def issue_code(subject: str, client_id: str, redirect_uri: str, state: str, nonce: str, code_challenge: str) -> RedirectResponse:
    if subject not in IDENTITIES or client_id != CLIENT_ID:
        raise HTTPException(status_code=400, detail="Unknown test identity")
    code = secrets.token_urlsafe(32)
    AUTHORIZATION_CODES[code] = {"subject": subject, "client_id": client_id, "redirect_uri": redirect_uri, "nonce": nonce, "code_challenge": code_challenge}
    return RedirectResponse(
        f"{redirect_uri}?{urlencode({'code': code, 'state': state})}",
        status_code=303,
    )


@app.post("/token")
def token(
    grant_type: str = Form(), code: str = Form(), redirect_uri: str = Form(),
    client_id: str = Form(), client_secret: str = Form(), code_verifier: str = Form(),
) -> dict[str, object]:
    attempt = AUTHORIZATION_CODES.pop(code, None)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    if grant_type != "authorization_code" or client_secret != CLIENT_SECRET or attempt is None or attempt["client_id"] != client_id or attempt["redirect_uri"] != redirect_uri or not secrets.compare_digest(challenge, attempt["code_challenge"]):
        raise HTTPException(status_code=400, detail="Invalid token request")
    identity = IDENTITIES[attempt["subject"]]
    now = int(time.time())
    claims = {"iss": ISSUER, "sub": identity.subject, "aud": client_id, "iat": now, "exp": now + 300, "nonce": attempt["nonce"], "email": identity.email, "email_verified": identity.email_verified, "name": identity.name}
    id_token = jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": KEY_ID})
    return {"access_token": secrets.token_urlsafe(24), "token_type": "Bearer", "expires_in": 300, "id_token": id_token}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
