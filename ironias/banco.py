"""Carga y selección de ejercicios del banco."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).parent / "data" / "ejercicios.json"

MODOS = ("reconocer", "interpretar", "producir")


class BancoInvalido(ValueError):
    """El fichero de ejercicios no cumple el formato esperado."""


@dataclass
class Ejercicio:
    id: str
    modo: str
    nivel: int
    tipo: str
    contexto: str
    explicacion: str
    enunciado: str = ""
    pregunta: str = ""
    opciones: list[str] = field(default_factory=list)
    respuesta: int | None = None
    pista: str = ""
    consigna: str = ""
    criterios: list[str] = field(default_factory=list)
    ejemplos: list[str] = field(default_factory=list)

    @property
    def es_opcion_multiple(self) -> bool:
        return self.modo in ("reconocer", "interpretar")

    @classmethod
    def desde_dict(cls, datos: dict) -> "Ejercicio":
        faltan = {"id", "modo", "nivel", "tipo", "contexto", "explicacion"} - set(datos)
        if faltan:
            raise BancoInvalido(f"ejercicio sin campos {sorted(faltan)}: {datos.get('id', '?')}")
        if datos["modo"] not in MODOS:
            raise BancoInvalido(f"modo desconocido en {datos['id']}: {datos['modo']}")

        ej = cls(**{k: v for k, v in datos.items() if k in cls.__dataclass_fields__})

        if ej.es_opcion_multiple:
            if len(ej.opciones) < 2:
                raise BancoInvalido(f"{ej.id}: hacen falta al menos dos opciones")
            if ej.respuesta is None or not 0 <= ej.respuesta < len(ej.opciones):
                raise BancoInvalido(f"{ej.id}: índice de respuesta fuera de rango")
        elif not ej.consigna:
            raise BancoInvalido(f"{ej.id}: un ejercicio de producir necesita consigna")
        return ej


def cargar(ruta: Path | str | None = None) -> list[Ejercicio]:
    """Lee el banco de ejercicios y lo valida."""
    ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BancoInvalido(f"no se encuentra el banco de ejercicios: {ruta}") from exc
    except json.JSONDecodeError as exc:
        raise BancoInvalido(f"JSON inválido en {ruta}: {exc}") from exc

    ejercicios = [Ejercicio.desde_dict(d) for d in datos.get("ejercicios", [])]
    if not ejercicios:
        raise BancoInvalido(f"{ruta} no contiene ejercicios")

    ids = [e.id for e in ejercicios]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        raise BancoInvalido(f"ids repetidos: {repetidos}")
    return ejercicios


def filtrar(
    ejercicios: list[Ejercicio],
    modo: str | None = None,
    nivel: int | None = None,
    tipo: str | None = None,
) -> list[Ejercicio]:
    return [
        e
        for e in ejercicios
        if (modo is None or e.modo == modo)
        and (nivel is None or e.nivel == nivel)
        and (tipo is None or e.tipo == tipo)
    ]


def seleccionar(
    ejercicios: list[Ejercicio],
    num: int,
    rng: random.Random | None = None,
    progreso: dict | None = None,
    repaso: bool = False,
) -> list[Ejercicio]:
    """Elige `num` ejercicios; en modo repaso prioriza fallados y no vistos."""
    rng = rng or random.Random()
    candidatos = list(ejercicios)
    rng.shuffle(candidatos)

    if repaso and progreso:
        def prioridad(ej: Ejercicio) -> tuple[int, int]:
            registro = progreso.get(ej.id)
            if registro is None:
                return (1, 0)  # nunca visto: después de los fallados
            fallos = registro.get("fallos", 0)
            aciertos = registro.get("aciertos", 0)
            if fallos > aciertos:
                return (0, -fallos)  # fallado con frecuencia: primero
            return (2, aciertos)  # ya dominado: al final
        candidatos.sort(key=prioridad)
    else:
        candidatos.sort(key=lambda e: e.nivel)

    return candidatos[:num]


def tipos(ejercicios: list[Ejercicio]) -> list[str]:
    return sorted({e.tipo for e in ejercicios})
