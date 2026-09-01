"""Interfaz de línea de comandos del entrenamiento de ironías."""

from __future__ import annotations

import argparse
import random
import sys

from . import __version__, banco, progreso as prog
from .sesion import NOMBRES_TIPO, Sesion, informe

BIENVENIDA = """\
ENTRENAMIENTO DE IRONÍAS
Tres modos: reconocer (¿hay ironía y de qué tipo?), interpretar (¿qué quiere
decir de verdad?) y producir (escríbela tú). Escribe «pista» para una ayuda
o «salir» para terminar y ver el informe."""


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m ironias",
        description="Entrenamiento práctico de ironía en español.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "ejemplos:\n"
            "  python -m ironias                        sesión mixta de 10 ejercicios\n"
            "  python -m ironias -n 5 -m reconocer      solo detección, 5 ejercicios\n"
            "  python -m ironias --nivel 3              únicamente los difíciles\n"
            "  python -m ironias --repaso               prioriza lo que fallaste\n"
            "  python -m ironias --stats                cómo llevas el progreso\n"
        ),
    )
    p.add_argument("-n", "--num", type=int, default=10, help="número de ejercicios (por defecto 10)")
    p.add_argument("-m", "--modo", choices=banco.MODOS, help="limita la sesión a un modo")
    p.add_argument("--nivel", type=int, choices=(1, 2, 3), help="limita la sesión a un nivel")
    p.add_argument("--tipo", help="limita la sesión a un tipo de ironía (ver --listar)")
    p.add_argument("--repaso", action="store_true", help="prioriza los ejercicios fallados")
    p.add_argument("--listar", action="store_true", help="muestra modos, niveles y tipos disponibles")
    p.add_argument("--stats", action="store_true", help="muestra tu progreso acumulado")
    p.add_argument("--reiniciar", action="store_true", help="borra el progreso guardado")
    p.add_argument("--semilla", type=int, help="fija el orden aleatorio (útil para repetir una sesión)")
    p.add_argument("--sin-color", action="store_true", help="desactiva los colores ANSI")
    p.add_argument("--sin-guardar", action="store_true", help="no escribe el progreso en disco")
    p.add_argument("--banco", help="ruta a un banco de ejercicios alternativo")
    p.add_argument("--progreso", help="ruta al fichero de progreso")
    p.add_argument("--version", action="version", version=f"ironias {__version__}")
    return p


def listar(ejercicios: list) -> str:
    lineas = ["Modos:"]
    for modo in banco.MODOS:
        lineas.append(f"  {modo:<14} {len(banco.filtrar(ejercicios, modo=modo))} ejercicios")
    lineas.append("\nNiveles:")
    for nivel in (1, 2, 3):
        lineas.append(f"  nivel {nivel}       {len(banco.filtrar(ejercicios, nivel=nivel))} ejercicios")
    lineas.append("\nTipos (--tipo):")
    for tipo in banco.tipos(ejercicios):
        n = len(banco.filtrar(ejercicios, tipo=tipo))
        lineas.append(f"  {tipo:<14} {NOMBRES_TIPO.get(tipo, tipo)} ({n})")
    return "\n".join(lineas)


def formatear_stats(datos: dict) -> str:
    if not datos["ejercicios"]:
        return "Todavía no hay progreso guardado. Lanza una sesión con: python -m ironias"
    lineas = [
        "PROGRESO ACUMULADO",
        f"  ejercicios vistos : {datos['ejercicios']}",
        f"  respuestas        : {datos['respuestas']}",
        f"  aciertos          : {datos['aciertos']} ({datos['porcentaje']}%)",
    ]
    if datos["pendientes"]:
        lineas.append(f"  por repasar       : {', '.join(datos['pendientes'])}")
        lineas.append("\nRepásalos con: python -m ironias --repaso")
    else:
        lineas.append("  por repasar       : nada pendiente")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    try:
        ejercicios = banco.cargar(args.banco)
    except banco.BancoInvalido as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.listar:
        print(listar(ejercicios))
        return 0

    ruta_progreso = args.progreso or None

    if args.reiniciar:
        if prog.guardar({}, ruta_progreso) is None:
            print("No se ha podido escribir el progreso.", file=sys.stderr)
            return 1
        print("Progreso borrado.")
        return 0

    guardado = prog.cargar(ruta_progreso)

    if args.stats:
        print(formatear_stats(prog.resumen(guardado)))
        return 0

    if args.num < 1:
        print("Error: --num debe ser al menos 1.", file=sys.stderr)
        return 1

    disponibles = banco.filtrar(ejercicios, modo=args.modo, nivel=args.nivel, tipo=args.tipo)
    if not disponibles:
        print("No hay ejercicios con esos filtros. Prueba con --listar.", file=sys.stderr)
        return 1

    elegidos = banco.seleccionar(
        disponibles,
        args.num,
        rng=random.Random(args.semilla),
        progreso=guardado,
        repaso=args.repaso,
    )

    color = not args.sin_color and sys.stdout.isatty()
    print(BIENVENIDA)
    if len(elegidos) < args.num:
        print(f"\n(Solo hay {len(elegidos)} ejercicios con esos filtros.)")

    sesion = Sesion(elegidos, color=color)
    resultados = sesion.ejecutar()
    print(informe(resultados))

    if resultados and not args.sin_guardar:
        for r in resultados:
            prog.registrar(guardado, r.ejercicio.id, r.acierto)
        if prog.guardar(guardado, ruta_progreso) is None:
            print("\n(Aviso: no se ha podido guardar el progreso.)", file=sys.stderr)
    return 0
