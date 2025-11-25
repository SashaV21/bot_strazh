# core/database.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import core.config as config

load_dotenv()

DATABASE_URL = config.DATABASE_URL
if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL не задан в .env")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    from core.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)