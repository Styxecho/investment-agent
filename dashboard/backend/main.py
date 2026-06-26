"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dashboard.backend.config import settings
from dashboard.backend.routers import indicators, factors, states, analysis

app = FastAPI(
    title="Investment Agent Dashboard API",
    description="API for macro state analysis dashboard",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(indicators.router, prefix=settings.API_V1_PREFIX)
app.include_router(factors.router, prefix=settings.API_V1_PREFIX)
app.include_router(states.router, prefix=settings.API_V1_PREFIX)
app.include_router(analysis.router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {
        "message": "Investment Agent Dashboard API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}
