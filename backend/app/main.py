# app/main.py

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from .db.session import get_db, test_connection
from .router_chat import router as router_chat_router

app = FastAPI(title="MarketGemini Router API")

# 🔹 Allow your Vite dev server to call FastAPI
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_chat_router)

@app.on_event("startup")
async def on_startup():
    await test_connection()

@app.get("/")
async def root():
    return {"message": "MarketGemini Router API is running"}

@app.get("/health/db")
async def db_health(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT 1"))
    value = result.scalar_one()
    return {"db": "ok", "value": value}
