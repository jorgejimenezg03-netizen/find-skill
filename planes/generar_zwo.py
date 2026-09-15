#!/usr/bin/env python3
"""Genera las sesiones estructuradas de bici en formato .zwo (Zwift).

Un .zwo se expresa en porcentaje de FTP, así que no hay que regenerarlo al
cambiar de test: basta con actualizar la FTP en la app. Lo importan Zwift,
Rouvy, Wahoo SYSTM, Garmin Connect e intervals.icu, y desde ahí se empujan
al ciclocomputador o al rodillo.

    python3 planes/generar_zwo.py --salida sesiones-bici
"""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape

# (nombre de fichero, título, descripción, [bloques])
# Bloques: ("warmup"|"cooldown", segundos, desde, hasta)
#          ("steady", segundos, potencia)
#          ("intervals", repeticiones, seg_on, pot_on, seg_off, pot_off)
SESIONES = [
    ("01-test-ftp", "Test de FTP · 20 minutos",
     "El test que fija todas tus zonas. Sal conservador y sube desde el minuto 5. "
     "Tu FTP es la potencia media de los 20 minutos multiplicada por 0,95.", [
        ("warmup", 1200, 0.50, 0.70),
        ("intervals", 3, 60, 1.05, 120, 0.50),
        ("steady", 300, 0.50),
        ("steady", 1200, 1.05),   # 20' a tope: el rodillo no manda, mandas tú
        ("cooldown", 600, 0.60, 0.40),
     ]),
    ("02-tempo-3x8", "Tempo · 3×8'",
     "Primer escalón de intensidad, semanas 6 a 11. A 85-90 rpm y en acoples.", [
        ("warmup", 900, 0.50, 0.70),
        ("intervals", 3, 30, 0.85, 30, 0.50),
        ("intervals", 3, 480, 0.885, 240, 0.50),
        ("cooldown", 600, 0.60, 0.40),
     ]),
    ("03-largo-3x12", "Rodaje largo con 3×12'",
     "El motor de la bici, semanas 9 a 16. Las series van dentro del rodaje y la "
     "recuperación es rodando en Z2, sin parar. Come cada 30 minutos.", [
        ("warmup", 2700, 0.55, 0.70),
        ("intervals", 3, 720, 0.83, 360, 0.65),
        ("steady", 1800, 0.65),
        ("cooldown", 600, 0.60, 0.40),
     ]),
    ("04-umbral-3x10", "Umbral · 3×10'",
     "Lo que mueve la FTP de 212 a 245 W, semanas 12 a 16. Duele y tiene que doler.", [
        ("warmup", 1200, 0.50, 0.70),
        ("intervals", 3, 60, 0.98, 120, 0.50),
        ("intervals", 3, 600, 0.955, 300, 0.50),
        ("cooldown", 600, 0.60, 0.40),
     ]),
    ("05-ritmo-2x25", "Ritmo de carrera · 2×25'",
     "Semanas 17 a 22. Sin salir de los acoples ni una vez: se entrena la posición "
     "tanto como la potencia.", [
        ("warmup", 1200, 0.50, 0.70),
        ("intervals", 2, 1500, 0.775, 480, 0.55),
        ("cooldown", 600, 0.60, 0.40),
     ]),
    ("06-rodaje-z2", "Rodaje Z2",
     "La sesión más repetida del plan y la que construye el motor. Debes poder "
     "hablar en frases completas de principio a fin.", [
        ("warmup", 600, 0.45, 0.60),
        ("steady", 4200, 0.65),
        ("cooldown", 600, 0.60, 0.40),
     ]),
    ("07-ladrillo-90km", "Ladrillo · 90 km a ritmo de carrera",
     "El ensayo general, semanas 17 a 22. Potencia plana: sin picos al adelantar ni "
     "abandonos en las bajadas. Bebe cada 15' y come cada 20'. Últimos 10' a 95 rpm.", [
        ("warmup", 900, 0.50, 0.70),
        ("steady", 10800, 0.775),
        ("steady", 600, 0.775),
        ("cooldown", 300, 0.60, 0.45),
     ]),
    ("08-afinado-3x10", "Afinado · 3×10' a ritmo",
     "Semana 23. Menos volumen, mismo ritmo: se recortan las series, no la velocidad.", [
        ("warmup", 900, 0.50, 0.70),
        ("intervals", 3, 600, 0.775, 300, 0.55),
        ("cooldown", 600, 0.60, 0.40),
     ]),
    ("09-activacion", "Activación · semana de carrera",
     "Los días previos. Corto, con toques de ritmo para despertar las piernas, "
     "y a casa con la sensación de que te has quedado con ganas.", [
        ("warmup", 900, 0.45, 0.65),
        ("intervals", 4, 180, 0.775, 180, 0.50),
        ("cooldown", 600, 0.55, 0.40),
     ]),
]


def bloques_xml(bloques: list[tuple]) -> str:
    fuera = []
    for b in bloques:
        if b[0] in ("warmup", "cooldown"):
            _, dur, lo, hi = b
            etiqueta = "Warmup" if b[0] == "warmup" else "Cooldown"
            fuera.append(f'    <{etiqueta} Duration="{dur}" PowerLow="{lo}" PowerHigh="{hi}"/>')
        elif b[0] == "steady":
            _, dur, pot = b
            fuera.append(f'    <SteadyState Duration="{dur}" Power="{pot}"/>')
        elif b[0] == "intervals":
            _, rep, on_s, on_p, off_s, off_p = b
            fuera.append(
                f'    <IntervalsT Repeat="{rep}" OnDuration="{on_s}" OffDuration="{off_s}"'
                f' OnPower="{on_p}" OffPower="{off_p}"/>')
    return "\n".join(fuera)


def escribir(destino: Path) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    escritos = []
    for slug, titulo, desc, bloques in SESIONES:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<workout_file>\n"
            "  <author>Plan 70.3 Monterrey</author>\n"
            f"  <name>{escape(titulo)}</name>\n"
            f"  <description>{escape(desc)}</description>\n"
            "  <sportType>bike</sportType>\n"
            "  <tags><tag name=\"70.3\"/></tags>\n"
            "  <workout>\n"
            f"{bloques_xml(bloques)}\n"
            "  </workout>\n"
            "</workout_file>\n"
        )
        ruta = destino / f"{slug}.zwo"
        ruta.write_text(xml, encoding="utf-8")
        escritos.append(ruta)
    return escritos


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera las sesiones de bici en .zwo")
    ap.add_argument("--salida", default="sesiones-bici", help="Carpeta de destino")
    a = ap.parse_args()
    for r in escribir(Path(a.salida)):
        dur = 0
        print(f"  {r}")
    print(f"\n{len(SESIONES)} sesiones en {a.salida}/")
    print("Se importan en Zwift, Rouvy, Wahoo SYSTM, Garmin Connect o intervals.icu.")
    print("Van en % de FTP, así que tras cada retest solo hay que actualizar la FTP en la app.")


if __name__ == "__main__":
    main()
