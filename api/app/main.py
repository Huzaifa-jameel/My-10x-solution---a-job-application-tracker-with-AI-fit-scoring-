"""FastAPI application: CORS, router registration, liveness."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, jobs, profile, usage

app = FastAPI(
    title="JobFit API",
    description="Job application tracker with AI fit-scoring.",
    version="0.1.0",
)

# Only the frontend origin is allowed. Never allow_origins=["*"] with
# credentials enabled.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(profile.router)
app.include_router(usage.router)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict[str, str]:
    """Unprotected liveness probe."""
    return {"status": "ok"}
