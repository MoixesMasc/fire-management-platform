"""Utilidades comunes compartidas entre microservicios."""
from datetime import datetime, timezone


def now_iso() -> str:
    """Retorna el timestamp UTC actual en formato ISO 8601."""
    return datetime.now(tz=timezone.utc).isoformat()
