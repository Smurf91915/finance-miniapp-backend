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
                "Я старалась, но сумму в сообщении не поймала. Напиши, например: `кофе 320`, `зарплата 120000`, `вклад 15000`.",
                "Не вижу сумму. Дай мне цифры, и будет магия: `кофе 320`, `зарплата 120000`, `вклад 15000`.",
                "Тут не хватило самой важной детали: суммы. Попробуй так: `кофе 320`, `зарплата 120000`, `вклад 15000`.",
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
            "Финансовая картина месяца, без драматических спецэффектов:",
            "Свежая сводка по бюджету. Всё как на ладони:",
            "Вот как сейчас выглядит денежный пейзаж:",
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
                "Цели пока не настроены. Самое время придумать, куда понесем деньги с достоинством.",
                "Целей пока нет. Значит, пространство для финансовых амбиций свободно.",
                "Пока без целей. Можно сказать, деньги еще не получили официальное направление.",
            )
        )
        return

    lines = [
        _pick(
            "Цели и накопления. Копилка держится бодро:",
            "Вот как поживают цели и запасы:",
            "Смотрим на накопления без лишней тревоги:",
        )
    ]
    for goal in goals:
        lines.append(f"{goal['name']}: {format_minor(goal['balance_minor'])}")
    await message.answer("\n".join(lines))


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    text = _pick(
        "На связи. Будем приручать финансы без Excel-страданий.\n"
        "Пиши так: `кофе 320`, `зарплата 120000`, `вклад 15000`, `облигации 5000`.\n"
        "Быстрые кнопки уже снизу, а Mini App живет кнопкой ниже и в меню бота.\n"
        "Команды: /month, /goals, /app. Поехали за красивой статистикой.",
        "Я в строю и готова считать деньги бережно, но без занудства.\n"
        "Можно писать так: `кофе 320`, `зарплата 120000`, `вклад 15000`, `облигации 5000`.\n"
        "Снизу уже ждут быстрые кнопки, а Mini App доступен кнопкой ниже и в меню.\n"
        "Команды: /month, /goals, /app.",
        "Финансовый штаб открыт.\n"
        "Пиши операции в духе `кофе 320`, `зарплата 120000`, `вклад 15000`, `облигации 5000`.\n"
        "Быстрые кнопки снизу, Mini App под рукой, статистика будет красивой.\n"
        "Команды: /month, /goals, /app.",
    )
    await message.answer(text, reply_markup=main_keyboard(settings.mini_app_url))


@router.message(Command("app"))
async def handle_app(message: Message) -> None:
    if settings.mini_app_url:
        await message.answer(
            _pick(
                "Открывай Mini App кнопкой ниже или через меню бота. Там всё серьезно, но без тоски.",
                "Mini App уже ждёт. Жми кнопку ниже или открывай его через меню бота.",
                "Путь в Mini App открыт: кнопка ниже или меню бота. Всё удобно, всё по делу.",
            ),
            reply_markup=main_keyboard(settings.mini_app_url),
        )
        return
    await message.answer(
        _pick(
            "Mini App пока не подключен. Чуть позже прикрутим ему торжественный вход.",
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
                "Сценарий дохода сбился с маршрута. Давай еще раз, уже без приключений.",
                "Потеряла контекст дохода по дороге. Запустим заново.",
                "Сценарий дохода распался на молекулы. Попробуй еще раз.",
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
                    "Не вижу сумму. Напиши число, например `10000`, или `0`. Деньги любят конкретику.",
                    "Тут нужна сумма числом, например `10000`, или `0`. Иначе резерв прячется в тумане.",
                    "Напиши просто число, например `10000`, или `0`. Без цифр я тут бессильна.",
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
            f"Доход записан: {format_minor(income['amount_minor'])}. Денежный поток одобряет.",
            f"Готово, доход {format_minor(income['amount_minor'])} уже в учете.",
            f"Записала доход на {format_minor(income['amount_minor'])}. Красота.",
        )
    ]
    if len(created) > 1:
        lines.append(
            _pick(
                f"В неприкосновенный запас ушло: {format_minor(created[1]['amount_minor'])}. Будущее довольно.",
                f"В резерв отправилось: {format_minor(created[1]['amount_minor'])}. Подушка стала мягче.",
                f"Запас пополнился на {format_minor(created[1]['amount_minor'])}. Финансовая броня крепчает.",
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
            "Напиши трату текстом, например `кофе 320` или `аренда 35000`. Честность перед бюджетом приветствуется.",
            "Скинь расход в виде `кофе 320` или `аренда 35000`. Бюджет любит правду.",
            "Пиши расход как `кофе 320` или `аренда 35000`. Я всё аккуратно запишу.",
        ),
        "Доход": _pick(
            "Напиши доход, например `зарплата 120000`. Такие сообщения я особенно уважаю.",
            "Пиши доход так: `зарплата 120000`. Люблю хорошие новости с цифрами.",
            "Скинь доход в формате `зарплата 120000`. Это мой любимый жанр сообщений.",
        ),
        "Вклад": _pick(
            "Напиши пополнение вклада, например `вклад 15000`. Капитал любит дисциплину.",
            "Пиши пополнение так: `вклад 15000`. Деньги оценят ответственное отношение.",
            "Скинь сумму вклада в виде `вклад 15000`. Капитал сам себя не вырастит.",
        ),
        "Облигации": _pick(
            "Напиши инвестицию, например `облигации 5000`. Пусть деньги тоже работают.",
            "Пиши инвестицию так: `облигации 5000`. Пускай капитал не ленится.",
            "Скинь инвестицию в формате `облигации 5000`. Заставим деньги шевелиться.",
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
                "Возвраты пока лучше оформлять через приложение, чтобы аккуратно привязать их к исходной покупке. Пусть бухгалтерская карма будет чиста.",
                "Возврат лучше сделать через приложение, чтобы не запутать историю операции. Финансовый дзен важен.",
                "С возвратами пока лучше идти в приложение. Так учет будет чище и спокойнее.",
            )
        )
        return

    if lowered.startswith("вклад") or lowered.startswith("запас"):
        amount_minor = extract_amount_minor(text)
        if amount_minor is None:
            await message.answer(
                _pick(
                    "Не вижу сумму. Пример: `вклад 15000`. Копилка без цифр грустит.",
                    "Тут нужна сумма. Например: `вклад 15000`. Иначе вклад остается лишь красивой идеей.",
                    "Добавь сумму, например `вклад 15000`. Копилка любит конкретику.",
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
                        f"Цель `{goal_name}` не найдена в базе. Похоже, она ушла в отпуск.",
                        f"Не нашла цель `{goal_name}`. Видимо, она временно вне зоны финансовой ответственности.",
                        f"Цель `{goal_name}` куда-то пропала. Без нее пополнение не проведу.",
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
                f"{goal_name}: {format_minor(created['amount_minor'])}. Маленький шаг для сообщения, мощный шаг для капитала.",
                f"Пополнение в цель `{goal_name}` записано: {format_minor(created['amount_minor'])}. Капитал растет прилично.",
                f"`{goal_name}` пополнен на {format_minor(created['amount_minor'])}. Деньги выглядят собранно.",
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
                f"Доход {format_minor(amount_minor)}. Отлично, деньги пришли.\nСколько отправила в неприкосновенный запас? Можно написать число или `0`.",
                f"Доход на {format_minor(amount_minor)} вижу. Красиво.\nСколько сразу откладываем в запас? Напиши число или `0`.",
                f"Поймала доход {format_minor(amount_minor)}.\nСколько отправляем в неприкосновенный запас? Подойдет число или `0`.",
            )
        )
        return

    if tx_type == "investment":
        if not parsed.get("category_id"):
            await message.answer(
                _pick(
                    "Не смогла определить инвестиционную категорию. Лучше открой приложение и направим капитал без суеты.",
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
                f"Инвестиция записана: {format_minor(created['amount_minor'])}. Пусть деньги теперь тоже ходят на работу.",
                f"Готово, инвестиция на {format_minor(created['amount_minor'])} учтена. Капитал не бездельничает.",
                f"Записала инвестицию: {format_minor(created['amount_minor'])}. Деньги официально трудоустроены.",
            )
        )
        return

    if tx_type == "expense":
        if not parsed.get("category_id"):
            await message.answer(
                _pick(
                    "Категорию не распознала. Проще открыть приложение и выбрать вручную, или напиши точнее, например `кофе 320`. Я умная, но не телепат.",
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
                f"{category_label}: {format_minor(created['amount_minor'])}. Записала и не осуждаю.",
                f"Готово: {category_label} на {format_minor(created['amount_minor'])}. Бюджет все видел, но держится.",
                f"Записала {category_label}: {format_minor(created['amount_minor'])}. Финансовая история запомнит этот день.",
            )
        )
        return

    await message.answer(
        _pick(
            "Пока не поняла тип операции. Но ничего, и великие бюджеты начинались с неловких формулировок. Лучше открой приложение.",
            "Смысл сообщения пока не поймала. Звучит загадочно. Если что, приложение поможет без лишней драмы.",
            "Не до конца поняла, что ты хотела записать. Такое бывает даже у умных ботов. Лучше открой приложение.",
        )
    )
