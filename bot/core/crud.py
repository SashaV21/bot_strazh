# core/crud.py
from sqlalchemy import select
from core.models import User, Submission
from core.database import async_session

# Импорт async_session внутри функций или внизу
from core.database import async_session

async def get_or_create_user(telegram_id: int, username: str | None = None) -> User:
    safe_username = username if username is not None else f"user_{telegram_id}"
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_id, username=safe_username)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

async def create_submission(
    user_id: int,
    content_type: str,
    raw_content: str,
    ai_response: str,
    ai_confidence: float,
    suspicious: bool
) -> Submission:
    async with async_session() as session:
        submission = Submission(
            user_id=user_id,
            content_type=content_type,
            raw_content=raw_content,
            ai_response=ai_response,
            ai_confidence=ai_confidence,
            suspicious=suspicious,
            reviewed_by_expert=False
        )
        session.add(submission)
        await session.commit()
        await session.refresh(submission)
        return submission
    


