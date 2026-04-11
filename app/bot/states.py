from aiogram.fsm.state import State, StatesGroup


class IncomeFlow(StatesGroup):
    waiting_for_reserve_amount = State()
