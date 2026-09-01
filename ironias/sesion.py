"""Motor de la sesión de entrenamiento."""

from __future__ import annotations

import string
import textwrap
from dataclasses import dataclass, field

from .banco import Ejercicio

LETRAS = string.ascii_lowercase

NOMBRES_TIPO = {
    "verbal": "ironía verbal",
    "situacional": "ironía situacional",
    "dramatica": "ironía dramática",
    "socratica": "ironía socrática",
    "estructural": "ironía estructural",
    "antifrasis": "antífrasis",
    "understatement": "atenuación irónica",
    "pragmatica": "uso y efecto",
    "literal": "no-ironía (control)",
}

ANCHO = 78


class Salir(Exception):
    """El usuario ha pedido terminar la sesión."""


@dataclass
class Resultado:
    ejercicio: Ejercicio
    acierto: bool
    respuesta: str = ""


class Sesion:
    """Ejecuta una lista de ejercicios sobre una entrada/salida inyectable."""

    def __init__(self, ejercicios, entrada=input, salida=print, color=True):
        self.ejercicios = ejercicios
        self.entrada = entrada
        self.salida = salida
        self.color = color
        self.resultados = []

    # --- presentación -------------------------------------------------
    def _c(self, texto: str, codigo: str) -> str:
        return f"\033[{codigo}m{texto}\033[0m" if self.color else texto

    def _parrafo(self, texto: str, sangria: str = "", colgante: str = "") -> None:
        for linea in texto.split("\n"):
            envuelto = textwrap.fill(
                linea,
                width=ANCHO,
                initial_indent=sangria,
                subsequent_indent=sangria + colgante,
            )
            self.salida(envuelto if linea.strip() else "")

    def _titulo(self, texto: str) -> None:
        self.salida("")
        self.salida(self._c(texto, "1;36"))
        self.salida(self._c("─" * min(len(texto), ANCHO), "36"))

    # --- ejecución ----------------------------------------------------
    def ejecutar(self) -> list[Resultado]:
        total = len(self.ejercicios)
        for i, ejercicio in enumerate(self.ejercicios, start=1):
            try:
                self._plantear(ejercicio, i, total)
            except (Salir, EOFError, KeyboardInterrupt):
                self.salida("\nSesión interrumpida. Guardando lo hecho hasta aquí.")
                break
        return self.resultados

    def _plantear(self, ej: Ejercicio, indice: int, total: int) -> None:
        etiqueta = f"[{indice}/{total}] {ej.modo.upper()} · nivel {ej.nivel} · {NOMBRES_TIPO.get(ej.tipo, ej.tipo)}"
        self._titulo(etiqueta)
        self._parrafo(ej.contexto)
        if ej.enunciado:
            self.salida("")
            self._parrafo(self._c(ej.enunciado, "1"), sangria="  ")

        if ej.es_opcion_multiple:
            self._opcion_multiple(ej)
        else:
            self._produccion(ej)

    def _opcion_multiple(self, ej: Ejercicio) -> None:
        self.salida("")
        self._parrafo(ej.pregunta or "¿Qué ocurre aquí?")
        for i, opcion in enumerate(ej.opciones):
            self._parrafo(f"{LETRAS[i]}) {opcion}", sangria="  ", colgante="   ")

        while True:
            bruto = self._preguntar("\nTu respuesta (letra, «pista» o «salir»): ")
            elegido = normalizar_opcion(bruto, len(ej.opciones))
            if elegido is None:
                if bruto.strip().lower().startswith("pist"):
                    self._parrafo(self._c(f"Pista: {ej.pista}", "33") if ej.pista else "No hay pista para este.")
                    continue
                self.salida("No te he entendido: responde con una letra.")
                continue
            break

        acierto = elegido == ej.respuesta
        if acierto:
            self.salida(self._c("\n✓ Correcto.", "1;32"))
        else:
            correcta = f"{LETRAS[ej.respuesta]}) {ej.opciones[ej.respuesta]}"
            self.salida(self._c("\n✗ No exactamente.", "1;31"))
            self._parrafo(f"Respuesta: {correcta}", sangria="  ")
        self._parrafo(ej.explicacion, sangria="  ")
        self.resultados.append(Resultado(ej, acierto, bruto.strip()))

    def _produccion(self, ej: Ejercicio) -> None:
        self.salida("")
        self._parrafo(self._c(ej.consigna, "1"))
        texto = self._preguntar("\nTu versión: ").strip()

        self.salida("")
        self._parrafo("Criterios de esta consigna:")
        for criterio in ej.criterios:
            self._parrafo(f"· {criterio}", sangria="  ", colgante="  ")
        if ej.ejemplos:
            self.salida("")
            self._parrafo("Versiones de referencia:")
            for ejemplo in ej.ejemplos:
                self._parrafo(ejemplo, sangria="  ")
        self.salida("")
        self._parrafo(ej.explicacion)

        autoev = self._preguntar("\n¿Tu versión cumple los criterios? (s/n): ").strip().lower()
        acierto = autoev.startswith("s")
        self.resultados.append(Resultado(ej, acierto, texto))

    def _preguntar(self, prompt: str) -> str:
        respuesta = self.entrada(prompt)
        if respuesta is None:
            raise Salir
        if respuesta.strip().lower() in ("salir", "quit", "exit", "q"):
            raise Salir
        return respuesta


def normalizar_opcion(bruto: str, num_opciones: int) -> int | None:
    """Acepta «a», «A)», «1» o «1.» y devuelve el índice, o None si no es válido."""
    limpio = bruto.strip().lower().rstrip(").-")
    if not limpio:
        return None
    if limpio.isdigit():
        indice = int(limpio) - 1
    elif len(limpio) == 1 and limpio in LETRAS:
        indice = LETRAS.index(limpio)
    else:
        return None
    return indice if 0 <= indice < num_opciones else None


def informe(resultados: list[Resultado]) -> str:
    """Resumen final: nota, desglose por modo y por tipo, y qué repasar."""
    if not resultados:
        return "No has completado ningún ejercicio."

    aciertos = sum(1 for r in resultados if r.acierto)
    total = len(resultados)
    pct = round(100 * aciertos / total)

    lineas = ["", "═" * ANCHO, f"RESULTADO: {aciertos}/{total} ({pct}%)", "═" * ANCHO]

    for clave, titulo in (("modo", "Por modo"), ("tipo", "Por tipo")):
        grupos: dict[str, list[Resultado]] = {}
        for r in resultados:
            grupos.setdefault(getattr(r.ejercicio, clave), []).append(r)
        lineas.append(f"\n{titulo}:")
        for nombre, rs in sorted(grupos.items()):
            ok = sum(1 for r in rs if r.acierto)
            etiqueta = NOMBRES_TIPO.get(nombre, nombre) if clave == "tipo" else nombre
            lineas.append(f"  {etiqueta:<24} {ok}/{len(rs)}")

    fallados = [r.ejercicio for r in resultados if not r.acierto]
    if fallados:
        lineas.append("\nPara repasar (usa --repaso en la próxima sesión):")
        for ej in fallados:
            lineas.append(f"  {ej.id}  {NOMBRES_TIPO.get(ej.tipo, ej.tipo)} · nivel {ej.nivel}")

    lineas.append("\n" + consejo(pct))
    return "\n".join(lineas)


def consejo(pct: int) -> str:
    if pct >= 90:
        return "Nivel alto: pasa a --nivel 3 y al modo producir, que es donde se nota de verdad."
    if pct >= 70:
        return "Buena base. Repasa los fallos con --repaso y sube de nivel."
    if pct >= 40:
        return "Vas encontrando el mecanismo. Insiste en reconocer antes de producir."
    return "Empieza por --nivel 1 --modo reconocer: primero detectar el contraste, luego lo demás."
