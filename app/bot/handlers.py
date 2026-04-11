from datetime import datetime, timezone

import httpx
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.api_client import BackendClient
from app.bot.keyboards import main_keyboard
from app.bot.states import IncomeFlow
from app.bot.utils import extract_amount_minor, format_minor
from app.core.config import settings

router = Router()


def _transaction_dt(message: Message) -> str:
    return (message.date or datetime.now(timezone.utc)).isoformat()


def _goal_by_name(goals: list[dict], name: str) -> dict | None:
    lowered = name.lower()
    for goal in goals:
        if str(goal["name"]).lower() == lowered:
            return goal
    return None


def _summary_lines(dashboard: dict) -> list[str]:
    return [
        f"Доходы: {format_minor(dashboard['income_total_minor'])}",
        f"Расходы: {format_minor(dashboard['expense_total_minor'])}",
        f"Инвестиции: {format_minor(dashboard['investment_total_minor'])}",
        f"Накопления: {format_minor(dashboard['goal_total_minor'])}",
        f"Возвраты: {format_minor(dashboard['refund_total_minor'])}",
        f"Доступно: {format_minor(dashboard['available_minor'])}",
    ]


async def _send_month_summary(message: Message, backend: BackendClient) -> None:
    try:
        dashboard = await backend.get_dashboard(message.from_user.id)
    except httpx.HTTPError as exc:
        await message.answer(f"Не удалось получить сводку: {exc}")
        return

    await message.answer("\n".join(_summary_lines(dashboard)))


async def _send_goals_summary(message: Message, backend: BackendClient) -> None:
    try:
        goals = await backend.list_goals(message.from_user.id)
    except httpx.HTTPError as exc:
        await message.answer(f"Не удалось получить цели: {exc}")
        return

    if not goals:
        await message.answer("Цели пока не настроены.")
        return

    lines = ["Цели и накопления:"]
    for goal in goals:
        lines.append(f"{goal['name']}: {format_minor(goal['balance_minor'])}")
    await message.answer("\n".join(lines))


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    text = (
        "Бот подключен.\n"
        "Можно писать так: `кофе 320`, `зарплата 120000`, `вклад 15000`, `облигации 5000`.\n"
        "Быстрые кнопки уже прикреплены снизу, а Mini App доступен кнопкой ниже и в меню бота.\n"
        "Команды: /month, /goals, /app."
    )
    await message.answer(text, reply_markup=main_keyboard(settings.mini_app_url))


@router.message(Command("app"))
async def handle_app(message: Message) -> None:
    if settings.mini_app_url:
        await message.answer(
            "Открой Mini App кнопкой ниже или через меню бота.",
            reply_markup=main_keyboard(settings.mini_app_url),
        )
        return
    await message.answer("MINI_APP_URL пока не настроен в `.env`.")


@router.message(Command("month"))
async def handle_month(message: Message, backend: BackendClient) -> None:
    await _send_month_summary(message, backend)


@router.message(Command("goals"))
async def handle_goals(message: Message, backend: BackendClient) -> None:
    await _send_goals_summary(message, backend)


@router.message(IncomeFlow.waiting_for_reserve_amount)
async def handle_reserve_amount(message: Message, state: FSMContext, backend: BackendClient) -> None:
    data = await state.get_data()
    income_payload = data.get("income_payload")
    if not income_payload:
        await state.clear()
        await message.answer("Сценарий дохода сброшен. Попробуй еще раз.")
        return

    reserve_text = (message.text or "").strip().lower()
    if reserve_text in {"0", "нет", "не откладывала", "пропустить", "-"}:
        reserve_amount_minor = None
    else:
        reserve_amount_minor = extract_amount_minor(reserve_text)
        if reserve_amount_minor is None:
            await message.answer("Не вижу сумму. Напиши число, например `10000`, или `0`.")
            return

    income_payload["reserve_amount_minor"] = reserve_amount_minor
    try:
        created = await backend.create_income(message.from_user.id, income_payload)
    except httpx.HTTPError as exc:
        await message.answer(f"Не удалось записать доход: {exc}")
        return
    finally:
        await state.clear()

    income = created[0]
    lines = [f"Доход записан: {format_minor(income['amount_minor'])}"]
    if len(created) > 1:
        lines.append(f"В неприкосновенный запас: {format_minor(created[1]['amount_minor'])}")
    await message.answer("\n".join(lines), reply_markup=main_keyboard(settings.mini_app_url))


@router.message(F.text.in_({"Сводка за месяц", "Цели и накопления"}))
async def handle_summary_shortcuts(message: Message, backend: BackendClient) -> None:
    if message.text == "Сводка за месяц":
        await _send_month_summary(message, backend)
        return
    await _send_goals_summary(message, backend)


@router.message(F.text.in_({"Расход", "Доход", "Вклад", "Облигации"}))
async def handle_shortcuts(message: Message) -> None:
    hints = {
        "Расход": "Напиши трату текстом, например `кофе 320` или `аренда 35000`.",
        "Доход": "Напиши доход, например `зарплата 120000`.",
        "Вклад": "Напиши пополнение вклада, например `вклад 15000`.",
        "Облигации": "Напиши инвестицию, например `облигации 5000`.",
    }
    await message.answer(hints[message.text])


@router.message(F.text)
async def handle_text(message: Message, state: FSMContext, backend: BackendClient) -> None:
    text = (message.text or "").strip()
    lowered = text.lower()

    if lowered.startswith("возврат"):
        await message.answer("Возвраты пока лучше оформлять через приложение, чтобы привязать их к исходной покупке.")
        return

    if lowered.startswith("вклад") or lowered.startswith("запас"):
        amount_minor = extract_amount_minor(text)
        if amount_minor is None:
            await message.answer("Не вижу сумму. Пример: `вклад 15000`.")
            return
        try:
            goals = await backend.list_goals(message.from_user.id)
            goal_name = "Вклад" if lowered.startswith("вклад") else "Неприкосновенный запас"
            goal = _goal_by_name(goals, goal_name)
            if goal is None:
                await message.answer(f"Цель `{goal_name}` не найдена в базе.")
                return
            created = await backend.allocate_to_goal(
                message.from_user.id,
                goal["id"],
                {
                    "amount_minor": amount_minor,
                    "currency": "RUB",
                    "occurred_at": _transaction_dt(message),
                    "note": text,
                    "source": "bot",
                },
            )
        except httpx.HTTPError as exc:
            await message.answer(f"Не удалось записать пополнение: {exc}")
            return

        await message.answer(f"{goal_name}: {format_minor(created['amount_minor'])}")
        return

    try:
        parsed = await backend.parse_text(message.from_user.id, text)
    except httpx.HTTPError as exc:
        await message.answer(f"Не удалось разобрать сообщение: {exc}")
        return

    tx_type = parsed["type"]
    amount_minor = parsed["amount_minor"]
    occurred_at = _transaction_dt(message)

    if tx_type == "income":
        await state.set_state(IncomeFlow.waiting_for_reserve_amount)
        await state.update_data(
            income_payload={
                "amount_minor": amount_minor,
                "currency": "RUB",
                "occurred_at": occurred_at,
                "note": parsed.get("note") or text,
                "source": "bot",
            }
        )
        await message.answer(
            f"Доход {format_minor(amount_minor)}. Сколько отправила в неприкосновенный запас?\n"
            "Можно написать число или `0`."
        )
        return

    if tx_type == "investment":
        if not parsed.get("category_id"):
            await message.answer("Не смогла определить инвестиционную категорию. Лучше открой приложение.")
            return
        try:
            created = await backend.create_investment(
                message.from_user.id,
                {
                    "amount_minor": amount_minor,
                    "currency": "RUB",
                    "occurred_at": occurred_at,
                    "category_id": parsed["category_id"],
                    "subcategory_id": parsed.get("subcategory_id"),
                    "note": parsed.get("note") or text,
                    "source": "bot",
                },
            )
        except httpx.HTTPError as exc:
            await message.answer(f"Не удалось записать инвестицию: {exc}")
            return
        await message.answer(f"Инвестиция записана: {format_minor(created['amount_minor'])}")
        return

    if tx_type == "expense":
        if not parsed.get("category_id"):
            await message.answer(
                "Категорию не распознала. Проще открыть приложение и выбрать вручную, "
                "или напиши точнее, например `кофе 320`."
            )
            return
        try:
            created = await backend.create_expense(
                message.from_user.id,
                {
                    "amount_minor": amount_minor,
                    "currency": "RUB",
                    "occurred_at": occurred_at,
                    "category_id": parsed["category_id"],
                    "subcategory_id": parsed.get("subcategory_id"),
                    "note": parsed.get("note") or text,
                    "source": "bot",
                },
            )
        except httpx.HTTPError as exc:
            await message.answer(f"Не удалось записать расход: {exc}")
            return

        category_label = created.get("subcategory_name") or created.get("category_name") or "Расход"
        await message.answer(f"{category_label}: {format_minor(created['amount_minor'])}")
        return

    await message.answer("Пока не поняла тип операции. Лучше открой приложение.")
