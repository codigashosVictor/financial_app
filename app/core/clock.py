from datetime import date, datetime
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("America/Mexico_City")


def today() -> date:
    """
    Fecha actual en la zona horaria de la app, no la del servidor.
    Railway corre en UTC, y Mexico City es UTC-6 sin horario de verano,
    así que usar date.today() directo adelanta la fecha (y a veces el
    periodo de corte) durante buena parte del día.
    """
    return datetime.now(APP_TZ).date()


def now() -> datetime:
    return datetime.now(APP_TZ)
