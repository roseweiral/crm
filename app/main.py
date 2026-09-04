"""FastAPI entry point for the CRM."""

from fastapi import FastAPI

from routers.contact_role_groups import router as contact_role_groups_router
from routers.contacts import router as contacts_router
from routers.family_units import router as family_units_router
from routers.reference_data import router as reference_data_router


app = FastAPI(title="Volunteer CRM API")
app.include_router(contacts_router, prefix="/api/v1")
app.include_router(family_units_router, prefix="/api/v1")
app.include_router(reference_data_router, prefix="/api/v1")
app.include_router(contact_role_groups_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is available."""
    return {"status": "ok"}
