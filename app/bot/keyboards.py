from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo


def main_keyboard(mini_app_url: str | None) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text="Расход"), KeyboardButton(text="Доход")],
        [KeyboardButton(text="Вклад"), KeyboardButton(text="Облигации")],
        [KeyboardButton(text="Сводка за месяц"), KeyboardButton(text="Цели и накопления")],
    ]
    if mini_app_url:
        rows.append([KeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=mini_app_url))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
