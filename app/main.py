"""FastAPI entry point for the CRM."""

from fastapi import FastAPI

from routers.contacts import router as contacts_router


app = FastAPI(title="Volunteer CRM API")
app.include_router(contacts_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is available."""
    return {"status": "ok"}
