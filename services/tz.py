"""Utilitários de data/hora no fuso horário de Brasília (America/Sao_Paulo)."""
from datetime import datetime, date
from zoneinfo import ZoneInfo

BR = ZoneInfo("America/Sao_Paulo")


def now_br() -> datetime:
    return datetime.now(BR)


def today_br() -> date:
    return datetime.now(BR).date()
