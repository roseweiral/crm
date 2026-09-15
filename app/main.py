"""FastAPI entry point for the CRM."""

import os

from authentication import get_current_user
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.address_book import router as address_book_router
from routers.authentication import router as authentication_router
from routers.contact_details import router as contact_details_router
from routers.contact_role_groups import router as contact_role_groups_router
from routers.contacts import router as contacts_router
from routers.documents import router as documents_router
from routers.family_units import router as family_units_router
from routers.reference_data import router as reference_data_router
from starlette.middleware.sessions import SessionMiddleware
from write_security import allowed_origins

app = FastAPI(title="Volunteer CRM API")
auth_session_secret = os.environ.get("AUTH_SESSION_SECRET")
secure_cookies = (
    os.environ.get("AUTH_COOKIE_SECURE", "").lower() in {"1", "true", "yes", "on"}
    or os.environ.get("APP_ENV") == "production"
)
if secure_cookies and (not auth_session_secret or len(auth_session_secret) < 32):
    raise RuntimeError("AUTH_SESSION_SECRET must contain at least 32 characters")
app.add_middleware(
    SessionMiddleware,
    secret_key=auth_session_secret or "development-only-change-me",
    session_cookie="crm_oidc",
    max_age=600,
    same_site="lax",
    https_only=secure_cookies,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["ETag", "Location"],
    allow_credentials=True,
)
protected = [Depends(get_current_user)]
app.include_router(contacts_router, prefix="/api/v1", dependencies=protected)
app.include_router(family_units_router, prefix="/api/v1", dependencies=protected)
app.include_router(reference_data_router, prefix="/api/v1", dependencies=protected)
app.include_router(contact_role_groups_router, prefix="/api/v1", dependencies=protected)
app.include_router(contact_details_router, prefix="/api/v1", dependencies=protected)
app.include_router(address_book_router, prefix="/api/v1", dependencies=protected)
app.include_router(documents_router, prefix="/api/v1", dependencies=protected)
app.include_router(authentication_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is available."""
    return {"status": "ok"}
