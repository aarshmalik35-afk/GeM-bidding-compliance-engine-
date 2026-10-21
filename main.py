from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.routes import router

app = FastAPI(
    title="GeM Bid Compliance Verification API",
    description="AI-powered compliance verification prototype for GeM procurement bidders.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "GeM Bid Compliance Verification API is running.",
        "docs": "/docs",
    }
