from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ChatAction
from handlers.common import read_image, read_PDF
from core.crud import get_or_create_user, create_submission
from core.models import User, Submission
from core.database import async_session
from sqlalchemy import select
from PIL import Image
import numpy as np
import aiohttp
import logging
import re
import core.config as config 
import asyncio
from pytz import timezone, UTC

moscow_tz = timezone('Europe/Moscow')

RAG_API_URL=config.RAG_API_URL
router = Router()

_sent_submissions_cache = {}

# === FSM для админки ===
class AdminReviewStates(StatesGroup):
    waiting_for_class = State()
    waiting_for_comment = State()
class OCRStates(StatesGroup):
    waiting_for_content = State()
    awaiting_confirmation = State()

def get_main_menu_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 ИИ анализ рекламы", callback_data="menu_ai")],
        [InlineKeyboardButton(text="📤 Отправленные на рассмотрение", callback_data="menu_sent")],
        [
            InlineKeyboardButton(text="📚 Полезные статьи", url="https://t.me/+bMfGP50ElTAxZTMy"),
            InlineKeyboardButton(text="ℹ️ О нас", callback_data="menu_about")
        ]
    ])

def get_back_to_menu_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")]
    ])

def get_confirmation_buttons():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Всё верно", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no")
        ],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")]
    ])


# === Суперадмин ID (для /addadmin) ===
SUPER_ADMIN_TELEGRAM_ID = int(config.SUPER_ADMIN_TELEGRAM_ID)  # ← тот же ID, что в add_admin.py

# === Команда /admin ===
@router.message(Command("admin"))
async def admin_login(message: types.Message, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user and user.is_admin:
            await message.answer("🔑 Вы вошли как администратор.")
            await show_pending_submissions(message)
        else:
            await message.answer("❌ Доступ запрещён.")

# === Показ запросов на модерацию ===
async def show_pending_submissions(message: types.Message):
    async with async_session() as session:
        result = await session.execute(
            select(Submission)
            .where(Submission.suspicious == True)
            .where(Submission.reviewed_by_expert == False)
            .order_by(Submission.created_at)
        )
        submissions = result.scalars().all()
        if not submissions:
            await message.answer("📭 Нет запросов на проверку.", reply_markup=get_back_to_menu_button())
            return

        for sub in submissions[:5]:
            preview = sub.raw_content 
            btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📝 Проверить",
                    callback_data=f"review_{sub.id}"
                )]
            ])
            await message.answer(
                f"📨 Запрос ID {sub.id}:\n<code>{preview}</code>",
                parse_mode="HTML",
                reply_markup=btn
            )

#=== Начало модерации ===
@router.callback_query(F.data.startswith("review_"))
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    sub_id = int(callback.data.split("_")[1])
    await state.update_data(submission_id=sub_id)
    await callback.message.answer("📝 Укажите класс объявления (например: законно / незаконно):")
    await state.set_state(AdminReviewStates.waiting_for_class)
    await callback.answer()

# === Ввод класса ===
@router.message(AdminReviewStates.waiting_for_class)
async def get_class(message: types.Message, state: FSMContext):
    await state.update_data(admin_class=message.text.strip())
    await message.answer("💬 Напишите комментарий:")
    await state.set_state(AdminReviewStates.waiting_for_comment)

# === Ввод комментария и завершение ===
@router.message(AdminReviewStates.waiting_for_comment)
async def get_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sub_id = data["submission_id"]
    admin_class = data["admin_class"]
    admin_comment = message.text.strip()
    final_answer = f"РЕЗУЛЬТАТ: {admin_class}\nКОММЕНТАРИЙ: {admin_comment}"

    async with async_session() as session:
        submission = await session.get(Submission, sub_id)
        if not submission:
            await message.answer("❌ Запрос не найден.")
            return
        submission.reviewed_by_expert = True
        #submission.suspicious = False
        submission.final_response = final_answer
        await session.commit()
        raw = submission.raw_content
        user = await session.get(User, submission.user_id)
        if user:
            try:
                await message.bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        "✅ Ваш запрос прошёл экспертную проверку!\n\n"
                        f"Запрос: {raw} \n\n"
                        f"<code>{final_answer}</code>\n\n"
                        "Вы можете посмотреть его в разделе «Отправленные на рассмотрение»."
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление пользователю {user.telegram_id}: {e}")

    await message.answer("✅ Ответ сохранён и отправлен пользователю.", reply_markup=get_back_to_menu_button())
    await state.clear()

# === Команда /addadmin (только для суперадмина) ===
@router.message(Command("addadmin"))
async def add_admin_cmd(message: types.Message):
    if message.from_user.id != SUPER_ADMIN_TELEGRAM_ID:
        await message.answer("❌ Только суперадмин может это делать.")
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("UsageId: /addadmin <user_id>\nПример: /addadmin 123456789")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть целым числом.")
        return

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == target_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Пользователь с таким ID не найден в базе.")
            return
        user.is_admin = True
        await session.commit()
        await message.answer(f"✅ Пользователь {user.username or user.telegram_id} теперь админ.")

@router.callback_query(F.data == "menu_sent")
async def show_user_submissions(callback: types.CallbackQuery):
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    async with async_session() as session:
        result = await session.execute(
            select(Submission)
            .where(Submission.user_id == user.id)
            .where(Submission.suspicious == True)
            .where(Submission.reviewed_by_expert == False)
            .order_by(Submission.created_at.desc())
        )
        pending_subs = result.scalars().all()

        if not pending_subs:
            await callback.message.answer(
                "📭 Нет запросов, ожидающих проверки.",
                reply_markup=get_back_to_menu_button()
            )
            await callback.answer()
            return

        subs_to_show = pending_subs[:5]
        for sub in subs_to_show:
            response = sub.final_response or sub.ai_response or "—"
            raw = sub.raw_content or "-"
            local_time = sub.created_at.astimezone(moscow_tz)
            await callback.message.answer(
                f"📄 Запрос от {local_time.strftime('%d.%m %H:%M')}:\n"
                f"Статус: ⏳ Ожидает проверки\n"
                f"Запрос: {raw}\n"
                f"<code>{response}</code>",
                parse_mode="HTML"
            )

        result_all = await session.execute(
            select(Submission)
            .where(Submission.user_id == user.id)
            .where(Submission.suspicious == True)
            .order_by(Submission.created_at.desc())
        )
        all_subs = result_all.scalars().all()
        shown_ids = {s.id for s in subs_to_show}
        remaining_ids = [s.id for s in all_subs if s.id not in shown_ids]

        _sent_submissions_cache[callback.from_user.id] = remaining_ids

        buttons = []
        if remaining_ids:
            buttons.append([InlineKeyboardButton(text="👇 Показать ещё (уже проверенные заявки)", callback_data="show_more_sent")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")])

        await callback.message.answer(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await callback.answer()

@router.callback_query(F.data == "show_more_sent")
async def show_more_sent(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    remaining_ids = _sent_submissions_cache.get(user_id)
    if not remaining_ids:
        await callback.message.answer("❌ Кэш устарел. Вернитесь в меню и откройте раздел заново.", reply_markup=get_back_to_menu_button())
        await callback.answer()
        return

    async with async_session() as session:
        result = await session.execute(select(Submission).where(Submission.id.in_(remaining_ids)))
        remaining_subs = result.scalars().all()
        remaining_subs.sort(key=lambda s: s.created_at, reverse=True)

        for sub in remaining_subs:
            status = "✅ Проверено экспертом" if sub.reviewed_by_expert else "⏳ Ожидает проверки"
            response = sub.final_response or sub.ai_response or "—"
            raw = sub.raw_content or "-"
            local_time = sub.created_at.astimezone(moscow_tz)
            await callback.message.answer(
                f"📄 Запрос от {local_time.strftime('%d.%m %H:%M')}:\n"
                f"Статус: {status}\n"
                f"Запрос: {raw}\n"
                f"<code>{response}</code>",
                parse_mode="HTML"
            )

        _sent_submissions_cache.pop(user_id, None)
        await callback.message.answer("✅ Все запросы показаны.", reply_markup=get_back_to_menu_button())
        await callback.answer()

# --- /start ---
@router.message(Command("start"))
async def start_handler(message: types.Message):
    await get_or_create_user(message.from_user.id, message.from_user.username)
    try:
        await message.answer_photo(
            photo=FSInputFile("welcome.jpg"),
            caption=(
                "🛡️ Добро пожаловать в бот «Страж»!\n\n"
                "Проверяйте рекламные материалы на соответствие законодательству РФ.\n"
                "Выберите действие:"
            ),
            reply_markup=get_main_menu_inline()
        )
    except FileNotFoundError:
        await message.answer(
            "⚠️ Фото не найдено (`welcome.jpg`).\n"
            "Но меню работает:",
            reply_markup=get_main_menu_inline()
        )

# --- Меню ---
@router.callback_query(F.data == "menu_ai")
async def ai_helper(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(OCRStates.waiting_for_content)
    await callback.message.answer(
        "📩 Отправьте текст, изображение текста (PNG/JPG) или PDF.",
        reply_markup=get_back_to_menu_button()
    )
    await callback.answer()

@router.callback_query(F.data == "menu_about")
async def about_us(callback: types.CallbackQuery):
    text = (
        "🛡️ <b>Бот «Страж»</b>\n\n"
        "Интеллектуальный помощник для проверки объявлений о сдаче жилья в аренду на соответствие закону РФ.\n\n"
        "Мы помогаем избежать:\n\n"
        "• Блокировки объявления;\n"
        "• Гражданско-правовой, административной и уголовной ответственности;\n"
        "• Других рисков, связанных с нарушением требований законодательства.\n\n"
        "💡 Бот анализирует текст, изображения текста и PDF-документы, "
        "выявляя потенциально спорные формулировки.\n\n"
        "<i>Разработано с заботой о юридической безопасности вашего бизнеса.\n\n</i>"
        "<i>Ответ ИИ \"Страж\" носит исключительно информационный характер и не является официальным правовым заключением</i>"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_back_to_menu_button())
    await callback.answer()

# @router.callback_query(F.data.in_({"menu_profile", "menu_articles"}))
# async def stub_handler(callback: types.CallbackQuery):
#     await callback.message.answer("🔜 Этот раздел пока в разработке.", reply_markup=get_back_to_menu_button())
#     await callback.answer()

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.answer_photo(
            photo=FSInputFile("welcome.jpg"),
            caption=(
                "🛡️ Добро пожаловать в бота «Страж»!\n\n"
                "Выберите действие:"
            ),
            reply_markup=get_main_menu_inline()
        )
    except FileNotFoundError:
        await callback.message.answer(
            "🛡️ Добро пожаловать в бота «Страж»!\n\n"
            "Выберите действие:",
            reply_markup=get_main_menu_inline()
        )
    await callback.answer()

# --- ИИ-анализа ---

async def ai_analysis(text: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(RAG_API_URL, json={"question": text}) as resp:
                if resp.status != 200:
                    raise ValueError(f"RAG API вернул статус {resp.status}")
                data = await resp.json()
                answer = data.get("answer", "").strip()
                if not answer:
                    raise ValueError("Пустой ответ от RAG")

                # Парсим результат по шаблону
                match = re.search(r"РЕЗУЛЬТАТ:\s*(.+)", answer, re.IGNORECASE)
                if not match:
                    # Если формат не распознан — считаем подозрительным
                    result_class = "требуется консультация"
                else:
                    result_class = match.group(1).strip().lower()

                # Определяем флаги
                if "требуется консультация" in result_class:
                    is_suspicious = True
                    confidence = 0.0
                elif "незаконно" in result_class:
                    is_suspicious = False
                    confidence = 0.3
                elif "законно" in result_class:
                    is_suspicious = False
                    confidence = 0.95
                else:
                    # Неизвестный класс — лучше перестраховаться
                    is_suspicious = True
                    confidence = 0.0

                return answer, confidence, is_suspicious

    except Exception as e:
        logging.error(f"Ошибка вызова RAG: {e}")
        return (
            "Не удалось проанализировать текст. Требуется ручная проверка.",
            0.0,
            True
        )
    

def _normalize_text(text: str) -> str:
    return (text or "(Текст не распознан)")[:3000]

# --- Обработка контента ---
@router.message(OCRStates.waiting_for_content, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1]
        file = await message.bot.download(photo.file_id)
        image = Image.open(file)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image_np = np.array(image)
        text = read_image(image_np)
        normalized = _normalize_text(text)
        await state.update_data(content_type="image", raw_content=normalized)
        await state.set_state(OCRStates.awaiting_confirmation)
        await message.answer(
            f"🔍 Распознанный текст:\n\n<code>{normalized}</code>",
            parse_mode="HTML",
            reply_markup=get_confirmation_buttons()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_back_to_menu_button())
        await state.clear()

@router.message(OCRStates.waiting_for_content, F.document.mime_type == "application/pdf")
async def handle_pdf(message: types.Message, state: FSMContext):
    try:
        doc = message.document
        if doc.file_size > 15 * 1024 * 1024:
            await message.answer("⚠️ Файл слишком большой (макс. 15 МБ).", reply_markup=get_back_to_menu_button())
            return
        file = await message.bot.download(doc.file_id)
        text = read_PDF(file)
        normalized = _normalize_text(text)
        await state.update_data(content_type="pdf", raw_content=normalized)
        await state.set_state(OCRStates.awaiting_confirmation)
        await message.answer(
            f"🔍 Распознанный текст:\n\n<code>{normalized}</code>",
            parse_mode="HTML",
            reply_markup=get_confirmation_buttons()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_back_to_menu_button())
        await state.clear()

# @router.message(OCRStates.waiting_for_content, F.text)
# async def handle_text(message: types.Message, state: FSMContext):
#     normalized = _normalize_text(message.text)
#     await state.update_data(content_type="text", raw_content=normalized)
#     await state.set_state(OCRStates.awaiting_confirmation)
#     await message.answer(
#         f"🔍 Ваш текст:\n\n<code>{normalized}</code>",
#         parse_mode="HTML",
#         reply_markup=get_confirmation_buttons()
#     )

@router.message(OCRStates.waiting_for_content, F.text)
async def handle_text_no_confirmation(message: types.Message, state: FSMContext):
    normalized = _normalize_text(message.text)
    await state.clear()

    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    
    async def keep_typing():
        while True:
            await asyncio.sleep(4)  
            try:
                await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
            except Exception:
                break  

    typing_task = asyncio.create_task(keep_typing())

    thinking_msg = await message.answer("⏳ Анализируем ваш запрос... Пожалуйста, подождите.")

    try:
        user = await get_or_create_user(message.from_user.id, message.from_user.username)
        ai_response, confidence, is_suspicious = await ai_analysis(normalized)

        await create_submission(
            user_id=user.id,
            content_type="text",
            raw_content=normalized,
            ai_response=ai_response,
            ai_confidence=confidence,
            suspicious=is_suspicious
        )

        base_text = f"🔍 Результат анализа:\n\n{ai_response}\n\n"

        if is_suspicious:
            additional_info = (
                "Этот запрос будет проверен специалистом. Ждите уведомлений!\n"
                "Посмотреть статус запроса можно в разделе \"Отправленные на рассмотрение\"."
            )
        else:
            additional_info = (
                "<a href='https://t.me/ADGuardINFO/5'>Полезные статьи</a>, которые изменят ваш подход к аренде"
            )

        
        typing_task.cancel()
        await thinking_msg.edit_text(
            base_text + additional_info,
            reply_markup=get_back_to_menu_button(),
            parse_mode="HTML"
        )

    except Exception as e:
        typing_task.cancel()
        await thinking_msg.edit_text(
            "❌ Произошла ошибка при анализе. Попробуйте позже.",
            reply_markup=get_back_to_menu_button()
        )
        logging.exception("Ошибка в handle_text_no_confirmation")

@router.callback_query(F.data == "confirm_yes", OCRStates.awaiting_confirmation)
async def confirm_yes(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    content_type = data.get("content_type")
    raw_content = data.get("raw_content")

    if not raw_content:
        await callback.message.answer("❌ Нет данных для анализа.", reply_markup=get_back_to_menu_button())
        await state.clear()
        return

    # Отправляем первое уведомление "печатает"
    await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)

    # Фоновая задача для поддержания индикатора "печатает"
    async def keep_typing():
        while True:
            await asyncio.sleep(4)
            try:
                await callback.bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)
            except Exception:
                break

    typing_task = asyncio.create_task(keep_typing())

    # Показываем текстовое сообщение ожидания
    thinking_msg = await callback.message.answer("⏳ Анализируем ваш запрос... Пожалуйста, подождите.")

    try:
        user = await get_or_create_user(callback.from_user.id, callback.from_user.username)
        ai_response, confidence, is_suspicious = await ai_analysis(raw_content)

        await create_submission(
            user_id=user.id,
            content_type=content_type,
            raw_content=raw_content,
            ai_response=ai_response,
            ai_confidence=confidence,
            suspicious=is_suspicious
        )

        base_text = f"🔍 Результат анализа:\n\n{ai_response}\n\n"

        if is_suspicious:
            additional_info = (
                "Этот запрос будет проверен специалистом. Ждите уведомлений!\n"
                "Посмотреть статус запроса можно в разделе \"Отправленные на рассмотрение\"."
            )
        else:
            # Исправлена ссылка: убраны лишние пробелы
            additional_info = (
                "<a href='https://t.me/ADGuardINFO/5'>Полезные статьи</a>, которые изменят ваш подход к аренде"
            )

        # Отменяем фоновую задачу и редактируем сообщение с ожиданием
        typing_task.cancel()
        await thinking_msg.edit_text(
            base_text + additional_info,
            reply_markup=get_back_to_menu_button(),
            parse_mode="HTML"
        )

    except Exception as e:
        typing_task.cancel()
        await thinking_msg.edit_text(
            "❌ Произошла ошибка при анализе. Попробуйте позже.",
            reply_markup=get_back_to_menu_button()
        )
        logging.exception("Ошибка в confirm_yes")

    await state.clear()
    

@router.callback_query(F.data == "confirm_no", OCRStates.awaiting_confirmation)
async def confirm_no(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(OCRStates.waiting_for_content)
    await callback.message.answer(
        "😔 Мы пока не можем обработать такой сложный файл. Отправьте текстом, изображение или PDF.",
        reply_markup=get_back_to_menu_button()
    )
    await callback.answer()