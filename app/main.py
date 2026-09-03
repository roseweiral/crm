"""FastAPI entry point for the CRM."""

from fastapi import FastAPI


app = FastAPI(title="Volunteer CRM API")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is available."""
    return {"status": "ok"}
