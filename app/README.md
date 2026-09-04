# API

This directory contains the FastAPI application for the CRM. The initial API exposes
`GET /health` so Docker and the test runner can verify that it is available.

The first read-only API routes are:

- `GET /api/v1/contacts`
- `GET /api/v1/contacts/{contact_id}`
