"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cinescout.api.routes import admin, cinemas, health, showings

# Create FastAPI app
app = FastAPI(
    title="CineScout API",
    description="Film showing aggregator for London cinemas",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],  # Frontend development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(cinemas.router, prefix="/api", tags=["cinemas"])
app.include_router(showings.router, prefix="/api", tags=["showings"])
app.include_router(admin.router, prefix="/api", tags=["admin"])
