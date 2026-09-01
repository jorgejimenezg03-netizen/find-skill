"""Progreso persistente entre sesiones (para el modo repaso)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def ruta_por_defecto() -> Path:
    """~/.find-skill/ironias-progreso.json, salvo que se indique otra con IRONIAS_PROGRESO."""
    env = os.environ.get("IRONIAS_PROGRESO")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".find-skill" / "ironias-progreso.json"


def cargar(ruta: Path | str | None = None) -> dict:
    ruta = Path(ruta) if ruta else ruta_por_defecto()
    if not ruta.exists():
        return {}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}  # un progreso corrupto no debe impedir entrenar
    return datos if isinstance(datos, dict) else {}


def guardar(progreso: dict, ruta: Path | str | None = None) -> Path | None:
    ruta = Path(ruta) if ruta else ruta_por_defecto()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(progreso, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return None
    return ruta


def registrar(progreso: dict, id_ejercicio: str, acierto: bool) -> dict:
    registro = progreso.setdefault(id_ejercicio, {"vistas": 0, "aciertos": 0, "fallos": 0})
    registro["vistas"] += 1
    registro["aciertos" if acierto else "fallos"] += 1
    registro["ultimo"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return progreso


def resumen(progreso: dict) -> dict:
    vistas = sum(r.get("vistas", 0) for r in progreso.values())
    aciertos = sum(r.get("aciertos", 0) for r in progreso.values())
    pendientes = sorted(
        (i for i, r in progreso.items() if r.get("fallos", 0) > r.get("aciertos", 0))
    )
    return {
        "ejercicios": len(progreso),
        "respuestas": vistas,
        "aciertos": aciertos,
        "porcentaje": round(100 * aciertos / vistas) if vistas else 0,
        "pendientes": pendientes,
    }
