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


def _backend_error_message(exc: httpx.HTTPError, fallback: str) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        detail: str | None = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            raw_detail = payload.get("detail")
            if isinstance(raw_detail, str) and raw_detail.strip():
                detail = raw_detail.strip()

        if response.status_code == 400 and detail == "Could not parse amount from text":
            return (
                "Я старалась, но сумму в сообщении не поймала. "
                "Напиши, например: `кофе 320`, `зарплата 120000`, `вклад 15000`."
            )

        if detail:
            return f"{fallback}: {detail}"

    return f"{fallback}: {exc}"


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
        "Финансовая картина месяца, без драматических спецэффектов:",
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
        await message.answer(_backend_error_message(exc, "Не удалось получить сводку"))
        return

    await message.answer("\n".join(_summary_lines(dashboard)))


async def _send_goals_summary(message: Message, backend: BackendClient) -> None:
    try:
        goals = await backend.list_goals(message.from_user.id)
    except httpx.HTTPError as exc:
        await message.answer(_backend_error_message(exc, "Не удалось получить цели"))
        return

    if not goals:
        await message.answer("Цели пока не настроены. Самое время придумать, куда понесем деньги с достоинством.")
        return

    lines = ["Цели и накопления. Копилка держится бодро:"]
    for goal in goals:
        lines.append(f"{goal['name']}: {format_minor(goal['balance_minor'])}")
    await message.answer("\n".join(lines))


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    text = (
        "На связи. Будем приручать финансы без Excel-страданий.\n"
        "Пиши так: `кофе 320`, `зарплата 120000`, `вклад 15000`, `облигации 5000`.\n"
        "Быстрые кнопки уже снизу, а Mini App живет кнопкой ниже и в меню бота.\n"
        "Команды: /month, /goals, /app. Поехали за красивой статистикой."
    )
    await message.answer(text, reply_markup=main_keyboard(settings.mini_app_url))


@router.message(Command("app"))
async def handle_app(message: Message) -> None:
    if settings.mini_app_url:
        await message.answer(
            "Открывай Mini App кнопкой ниже или через меню бота. Там всё серьезно, но без тоски.",
            reply_markup=main_keyboard(settings.mini_app_url),
        )
        return
    await message.answer("Mini App пока не подключен. Чуть позже прикрутим ему торжественный вход.")


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
        await message.answer("Сценарий дохода сбился с маршрута. Давай еще раз, уже без приключений.")
        return

    reserve_text = (message.text or "").strip().lower()
    if reserve_text in {"0", "нет", "не откладывала", "пропустить", "-"}:
        reserve_amount_minor = None
    else:
        reserve_amount_minor = extract_amount_minor(reserve_text)
        if reserve_amount_minor is None:
            await message.answer("Не вижу сумму. Напиши число, например `10000`, или `0`. Деньги любят конкретику.")
            return

    income_payload["reserve_amount_minor"] = reserve_amount_minor
    try:
        created = await backend.create_income(message.from_user.id, income_payload)
    except httpx.HTTPError as exc:
        await message.answer(_backend_error_message(exc, "Не удалось записать доход"))
        return
    finally:
        await state.clear()

    income = created[0]
    lines = [f"Доход записан: {format_minor(income['amount_minor'])}. Денежный поток одобряет."]
    if len(created) > 1:
        lines.append(f"В неприкосновенный запас ушло: {format_minor(created[1]['amount_minor'])}. Будущее довольно.")
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
        "Расход": "Напиши трату текстом, например `кофе 320` или `аренда 35000`. Честность перед бюджетом приветствуется.",
        "Доход": "Напиши доход, например `зарплата 120000`. Такие сообщения я особенно уважаю.",
        "Вклад": "Напиши пополнение вклада, например `вклад 15000`. Капитал любит дисциплину.",
        "Облигации": "Напиши инвестицию, например `облигации 5000`. Пусть деньги тоже работают.",
    }
    await message.answer(hints[message.text])


@router.message(F.text)
async def handle_text(message: Message, state: FSMContext, backend: BackendClient) -> None:
    text = (message.text or "").strip()
    lowered = text.lower()

    if lowered.startswith("возврат"):
        await message.answer(
            "Возвраты пока лучше оформлять через приложение, чтобы аккуратно привязать их к исходной покупке. "
            "Пусть бухгалтерская карма будет чиста."
        )
        return

    if lowered.startswith("вклад") or lowered.startswith("запас"):
        amount_minor = extract_amount_minor(text)
        if amount_minor is None:
            await message.answer("Не вижу сумму. Пример: `вклад 15000`. Копилка без цифр грустит.")
            return
        try:
            goals = await backend.list_goals(message.from_user.id)
            goal_name = "Вклад" if lowered.startswith("вклад") else "Неприкосновенный запас"
            goal = _goal_by_name(goals, goal_name)
            if goal is None:
                await message.answer(f"Цель `{goal_name}` не найдена в базе. Похоже, она ушла в отпуск.")
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
            await message.answer(_backend_error_message(exc, "Не удалось записать пополнение"))
            return

        await message.answer(
            f"{goal_name}: {format_minor(created['amount_minor'])}. Маленький шаг для сообщения, мощный шаг для капитала."
        )
        return

    try:
        parsed = await backend.parse_text(message.from_user.id, text)
    except httpx.HTTPError as exc:
        await message.answer(_backend_error_message(exc, "Не удалось разобрать сообщение"))
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
            f"Доход {format_minor(amount_minor)}. Отлично, деньги пришли.\n"
            "Сколько отправила в неприкосновенный запас? Можно написать число или `0`."
        )
        return

    if tx_type == "investment":
        if not parsed.get("category_id"):
            await message.answer("Не смогла определить инвестиционную категорию. Лучше открой приложение и направим капитал без суеты.")
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
            await message.answer(_backend_error_message(exc, "Не удалось записать инвестицию"))
            return
        await message.answer(f"Инвестиция записана: {format_minor(created['amount_minor'])}. Пусть деньги теперь тоже ходят на работу.")
        return

    if tx_type == "expense":
        if not parsed.get("category_id"):
            await message.answer(
                "Категорию не распознала. Проще открыть приложение и выбрать вручную, "
                "или напиши точнее, например `кофе 320`. Я умная, но не телепат."
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
            await message.answer(_backend_error_message(exc, "Не удалось записать расход"))
            return

        category_label = created.get("subcategory_name") or created.get("category_name") or "Расход"
        await message.answer(f"{category_label}: {format_minor(created['amount_minor'])}. Записала и не осуждаю.")
        return

    await message.answer("Пока не поняла тип операции. Но ничего, и великие бюджеты начинались с неловких формулировок. Лучше открой приложение.")
