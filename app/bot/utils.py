import re


def format_minor(amount_minor: int) -> str:
    amount = amount_minor / 100
    formatted = f"{amount:,.2f}".replace(",", " ").replace(".00", "")
    return f"{formatted} ₽"


def extract_amount_minor(text: str) -> int | None:
    match = re.search(r"(\d[\d\s]*)$", text.strip().lower())
    if match is None:
        return None
    return int(match.group(1).replace(" ", "")) * 100
