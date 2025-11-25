# bot/add_admin.py
import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import select

from core.database import async_session, init_db
from core.models import User

load_dotenv()

SUPER_ADMIN_TELEGRAM_ID = 353942250 

async def main():
    await init_db()
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == SUPER_ADMIN_TELEGRAM_ID)
        )
        user = result.scalar_one_or_none()
        if user:
            user.is_admin = True
            await session.commit()
            print(f"✅ Пользователь {user.username} теперь админ.")
        else:
            new_user = User(
                telegram_id=SUPER_ADMIN_TELEGRAM_ID,
                username="superadmin",
                is_admin=True
            )
            session.add(new_user)
            await session.commit()
            print("✅ Суперадмин добавлен в БД.")
    await session.close()

if __name__ == "__main__":
    asyncio.run(main())