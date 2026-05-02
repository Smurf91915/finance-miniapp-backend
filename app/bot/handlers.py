from datetime import datetime, timezone
from random import choice

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


def _pick(*variants: str) -> str:
    return choice(list(variants))


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
            return _pick(
                "Не вижу сумму в сообщении. Попробуй так: `кофе 320`, `зарплата 120000`, `вклад 15000`.",
                "Тут не хватает суммы. Напиши, например: `кофе 320`, `зарплата 120000`, `вклад 15000`.",
                "Похоже, сумма не распозналась. Можно так: `кофе 320`, `зарплата 120000`, `вклад 15000`.",
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
        _pick(
            "Сводка за период:",
            "Текущая картина по бюджету:",
            "Вот что сейчас по цифрам:",
        ),
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
        await message.answer(
            _pick(
                "Цели пока не настроены. Можно как раз выбрать, ради чего копим дальше.",
                "Пока без целей. Самое время задать деньгам направление.",
                "Целей еще нет. Значит, можно спокойно придумать следующую финансовую точку роста.",
            )
        )
        return

    lines = [
        _pick(
            "Цели и накопления:",
            "Текущее состояние целей:",
            "Вот как сейчас выглядят накопления:",
        )
    ]
    for goal in goals:
        lines.append(f"{goal['name']}: {format_minor(goal['balance_minor'])}")
    await message.answer("\n".join(lines))


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    text = _pick(
        "На связи. Будем вести финансы спокойно и по делу.\n"
        "Пиши так: `кофе 320`, `зарплата 120000`, `вклад 15000`, `облигации 5000`.\n"
        "Быстрые кнопки уже снизу, а Mini App живет кнопкой ниже и в меню бота.\n"
        "Команды: /month, /goals, /app.",
        "Я в строю и готова держать бюджет в порядке.\n"
        "Можно писать так: `кофе 320`, `зарплата 120000`, `вклад 15000`, `облигации 5000`.\n"
        "Снизу уже ждут быстрые кнопки, а Mini App доступен кнопкой ниже и в меню.\n"
        "Команды: /month, /goals, /app.",
        "Финансовый учет открыт.\n"
        "Пиши операции в духе `кофе 320`, `зарплата 120000`, `вклад 15000`, `облигации 5000`.\n"
        "Быстрые кнопки снизу, Mini App под рукой.\n"
        "Команды: /month, /goals, /app.",
    )
    await message.answer(text, reply_markup=main_keyboard(settings.mini_app_url))


@router.message(Command("app"))
async def handle_app(message: Message) -> None:
    if settings.mini_app_url:
        await message.answer(
            _pick(
                "Открывай Mini App кнопкой ниже или через меню бота.",
                "Mini App уже ждёт. Жми кнопку ниже или открывай его через меню бота.",
                "Путь в Mini App открыт: кнопка ниже или меню бота.",
            ),
            reply_markup=main_keyboard(settings.mini_app_url),
        )
        return
    await message.answer(
        _pick(
            "Mini App пока не подключен. Подтянем его чуть позже.",
            "Mini App пока молчит. Подключим его чуть позже.",
            "Mini App еще не на месте, но это временно.",
        )
    )


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
        await message.answer(
            _pick(
                "Сценарий дохода сбился. Давай попробуем еще раз.",
                "Потеряла контекст дохода по дороге. Запустим заново.",
                "Контекст дохода потерялся. Начнем заново.",
            )
        )
        return

    reserve_text = (message.text or "").strip().lower()
    if reserve_text in {"0", "нет", "не откладывала", "пропустить", "-"}:
        reserve_amount_minor = None
    else:
        reserve_amount_minor = extract_amount_minor(reserve_text)
        if reserve_amount_minor is None:
            await message.answer(
                _pick(
                    "Не вижу сумму. Напиши число, например `10000`, или `0`.",
                    "Тут нужна сумма числом, например `10000`, или `0`.",
                    "Напиши просто число, например `10000`, или `0`.",
                )
            )
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
    lines = [
        _pick(
            f"Доход записан: {format_minor(income['amount_minor'])}. Отличное движение.",
            f"Готово, доход {format_minor(income['amount_minor'])} уже в учете.",
            f"Записала доход на {format_minor(income['amount_minor'])}. Сильный результат.",
        )
    ]
    if len(created) > 1:
        lines.append(
            _pick(
                f"В неприкосновенный запас ушло: {format_minor(created[1]['amount_minor'])}. Хороший шаг.",
                f"В резерв отправилось: {format_minor(created[1]['amount_minor'])}. Подушка стала крепче.",
                f"Запас пополнился на {format_minor(created[1]['amount_minor'])}. Отлично.",
            )
        )
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
        "Расход": _pick(
            "Напиши трату текстом, например `кофе 320` или `аренда 35000`.",
            "Скинь расход в виде `кофе 320` или `аренда 35000`.",
            "Пиши расход как `кофе 320` или `аренда 35000`.",
        ),
        "Доход": _pick(
            "Напиши доход, например `зарплата 120000`.",
            "Пиши доход так: `зарплата 120000`.",
            "Скинь доход в формате `зарплата 120000`.",
        ),
        "Вклад": _pick(
            "Напиши пополнение вклада, например `вклад 15000`.",
            "Пиши пополнение так: `вклад 15000`.",
            "Скинь сумму вклада в виде `вклад 15000`.",
        ),
        "Облигации": _pick(
            "Напиши инвестицию, например `облигации 5000`.",
            "Пиши инвестицию так: `облигации 5000`.",
            "Скинь инвестицию в формате `облигации 5000`.",
        ),
    }
    await message.answer(hints[message.text])


@router.message(F.text)
async def handle_text(message: Message, state: FSMContext, backend: BackendClient) -> None:
    text = (message.text or "").strip()
    lowered = text.lower()

    if lowered.startswith("возврат"):
        await message.answer(
            _pick(
                "Возвраты пока лучше оформлять через приложение, чтобы аккуратно привязать их к исходной покупке.",
                "Возврат лучше сделать через приложение, чтобы не запутать историю операции.",
                "С возвратами пока лучше идти в приложение. Так учет будет чище и спокойнее.",
            )
        )
        return

    if lowered.startswith("вклад") or lowered.startswith("запас"):
        amount_minor = extract_amount_minor(text)
        if amount_minor is None:
            await message.answer(
                _pick(
                    "Не вижу сумму. Пример: `вклад 15000`.",
                    "Тут нужна сумма. Например: `вклад 15000`.",
                    "Добавь сумму, например `вклад 15000`.",
                )
            )
            return
        try:
            goals = await backend.list_goals(message.from_user.id)
            goal_name = "Вклад" if lowered.startswith("вклад") else "Неприкосновенный запас"
            goal = _goal_by_name(goals, goal_name)
            if goal is None:
                await message.answer(
                    _pick(
                        f"Цель `{goal_name}` не найдена в базе. Проверь, настроена ли она в приложении.",
                        f"Не нашла цель `{goal_name}`. Возможно, ее еще не создали.",
                        f"Цель `{goal_name}` сейчас недоступна. Лучше проверить ее в приложении.",
                    )
                )
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
            _pick(
                f"{goal_name}: {format_minor(created['amount_minor'])}. Еще один шаг к цели.",
                f"Пополнение в цель `{goal_name}` записано: {format_minor(created['amount_minor'])}. Движение хорошее.",
                f"`{goal_name}` пополнен на {format_minor(created['amount_minor'])}. Так цель становится ближе.",
            )
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
            _pick(
                f"Доход {format_minor(amount_minor)} вижу.\nСколько отправила в неприкосновенный запас? Можно написать число или `0`.",
                f"Доход на {format_minor(amount_minor)} зафиксирован.\nСколько сразу откладываем в запас? Напиши число или `0`.",
                f"Поймала доход {format_minor(amount_minor)}.\nСколько отправляем в неприкосновенный запас? Подойдет число или `0`.",
            )
        )
        return

    if tx_type == "investment":
        if not parsed.get("category_id"):
            await message.answer(
                _pick(
                    "Не смогла определить инвестиционную категорию. Лучше открыть приложение и выбрать ее вручную.",
                    "Инвестиционную категорию тут не распознала. Через приложение будет точнее.",
                    "С инвестиционной категорией вышла заминка. Проще открыть приложение и выбрать вручную.",
                )
            )
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
        await message.answer(
            _pick(
                f"Инвестиция записана: {format_minor(created['amount_minor'])}. Хорошее движение вперед.",
                f"Готово, инвестиция на {format_minor(created['amount_minor'])} учтена. Так капитал работает на тебя.",
                f"Записала инвестицию: {format_minor(created['amount_minor'])}. Последовательно и сильно.",
            )
        )
        return

    if tx_type == "expense":
        if not parsed.get("category_id"):
            await message.answer(
                _pick(
                    "Категорию не распознала. Проще открыть приложение и выбрать вручную, или напиши точнее, например `кофе 320`.",
                    "Категория тут расплывчатая. Либо уточни формулировку, например `кофе 320`, либо открой приложение.",
                    "Не уловила категорию расхода. Попробуй точнее, вроде `кофе 320`, или выбери вручную в приложении.",
                )
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
        await message.answer(
            _pick(
                f"{category_label}: {format_minor(created['amount_minor'])}. Записала.",
                f"Готово: {category_label} на {format_minor(created['amount_minor'])}.",
                f"Записала {category_label}: {format_minor(created['amount_minor'])}.",
            )
        )
        return

    await message.answer(
        _pick(
            "Пока не поняла тип операции. Если хочешь, можно открыть приложение и выбрать всё вручную.",
            "Смысл сообщения пока не поймала. Приложение поможет оформить операцию точнее.",
            "Не до конца поняла, что именно нужно записать. В приложении это можно сделать вручную.",
        )
    )
