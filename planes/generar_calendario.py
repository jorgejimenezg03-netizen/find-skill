#!/usr/bin/env python3
"""Expande el plan de 25 semanas en sesiones individuales (CSV e ICS).

Los objetivos de cada sesión se calculan a partir de tus tests, así que
al repetirlos en las semanas 9 y 17 basta con volver a lanzar el script
con los números nuevos.

    python3 planes/generar_calendario.py --ftp 215 --css 2:20 --umbral 5:30
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

INICIO = date(2026, 9, 7)  # lunes de la semana 1
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

# semana: (nº, bloque, horas, plantilla, foco)
SEMANAS = [
    (1, "Test", 11, "test", "Tests de las tres disciplinas. Se montan los acoples"),
    (2, "Base 1", 12, "base", "Primera semana con zonas. Adaptación a los acoples"),
    (3, "Base 1", 13, "base", "Rodaje largo a 2:45, ya en acoples"),
    (4, "Base 1", 14, "base", "Primera semana de carga dirigida"),
    (5, "Descarga", 9, "base", "Asimilación"),
    (6, "Base 2", 14, "base", "Última semana solo aeróbica"),
    (7, "Construcción 1", 15, "constr", "Entra el tempo"),
    (8, "Construcción 1", 15, "constr", "Empiezan las transiciones cronometradas"),
    (9, "Descarga + test", 10, "test", "Se repiten los tres tests"),
    (10, "Construcción 1", 15, "constr", "Bloques de 3×12'. Nutrición: 50 g/h"),
    (11, "Construcción 1", 16, "constr", "Rodaje largo a 3:15"),
    (12, "Construcción 1", 16, "constr", "Nutrición a 65 g/h"),
    (13, "Descarga", 10, "constr", "Asimilación sin perder ritmos"),
    (14, "Construcción 2", 15, "constr", "Umbral en bici: 3×10' al 95 %"),
    (15, "Construcción 2", 16, "constr", "Semana más dura del bloque"),
    (16, "Descarga navideña", 9, "constr", "Semana ligera y flexible"),
    (17, "Construcción 2 + test", 14, "test", "Tests. Se fija el objetivo definitivo"),
    (18, "Específico 1", 16, "espec", "Todo a ritmo de carrera"),
    (19, "Específico 1", 16, "espec", "Ladrillo completo con material de carrera"),
    (20, "Específico 1", 15, "espec", "Nado en aguas abiertas"),
    (21, "Descarga + competición", 11, "espec", "Carrera de preparación"),
    (22, "Específico 2", 16, "espec", "Ladrillo de 3:45. Semana pico"),
    (23, "Específico 2", 14, "espec", "Última semana de carga"),
    (24, "Afinado", 11, "taper", "Baja el volumen, se mantienen los ritmos"),
    (25, "Carrera", 6, "carrera", "Domingo: 5:13"),
]

# Trayectoria de peso: (última semana del tramo, kg por semana).
# El déficit aprieta en otoño, cuando la carga es baja, y se detiene en la
# semana 21: la semana pico, el simulacro y el afinado se comen completos.
TRAYECTORIA_PESO = [(9, 0.55), (17, 0.45), (21, 0.35), (25, 0.0)]


def pesos_objetivo(inicial: float) -> dict[int, float]:
    """Peso objetivo al final de cada semana del plan."""
    peso, fuera, tramo = inicial, {}, 0
    for n, _, _, _, _ in SEMANAS:
        while n > TRAYECTORIA_PESO[tramo][0]:
            tramo += 1
        peso -= TRAYECTORIA_PESO[tramo][1]
        fuera[n] = round(peso, 1)
    return fuera


# plantilla: (día, disciplina, título, minutos, objetivo, descripción)
# `objetivo` usa marcadores que se sustituyen por tus números: {z2}, {tempo}...
PLANTILLAS: dict[str, tuple[int, list[tuple]]] = {
    "base": (13 * 60, [
        (0, "Nado", "Técnica", 60, "{nado_z2}", "8×50 con tabla, 8×50 con pull. Foco en cadera alta"),
        (0, "Fuerza", "Fuerza máxima", 45, "", "Sentadilla, peso muerto rumano, remo, core. 4×6"),
        (1, "Bici", "Rodaje Z2", 90, "{z2}", "Continuo, 30' en acoples"),
        (1, "Carrera", "Suave", 35, "{run_z2}", "Conversando de principio a fin"),
        (2, "Nado", "Series cortas", 60, "{nado_umbral}", "16×50 r15\". Grábate cada tres semanas"),
        (2, "Carrera", "Suave + zancadas", 50, "{run_z2}", "6×20\" de zancadas al final"),
        (3, "Bici", "Rodaje Z2", 105, "{z2}", "Entero en acoples"),
        (3, "Fuerza", "Fuerza máxima", 45, "", "Dominadas, remo, core antirrotación"),
        (4, "Nado", "Técnica y velocidad", 60, "{nado_vo2}", "16×25 máximos r20\""),
        (5, "Bici", "Rodaje largo", 165, "{z2}", "Llano y en acoples. Come cada 30'"),
        (5, "Carrera", "Ladrillo", 15, "{run_z2}", "Muy suave, saliendo de la bici"),
        (6, "Carrera", "Larga", 75, "{run_z2}", "Ritmo plano, sin variaciones"),
    ]),
    "constr": (16 * 60, [
        (0, "Nado", "Técnica", 60, "{nado_z2}", "Drills y series cortas"),
        (0, "Fuerza", "Fuerza máxima", 45, "", "4×6 al 80-85 %"),
        (1, "Bici", "Tempo 3×8'", 105, "{tempo}", "r4' entre series. En acoples"),
        (1, "Carrera", "Ladrillo", 25, "{run_z2}", "Saliendo de la bici"),
        (2, "Carrera", "Tempo 4×5'", 70, "{run_tempo}", "r2' entre series"),
        (2, "Nado", "8×100", 60, "{nado_umbral}", "r20\""),
        (3, "Bici", "Rodaje Z2", 120, "{z2}", "En acoples todo el rato"),
        (3, "Fuerza", "Fuerza + transiciones", 60, "", "40' de fuerza + 20' de transiciones cronometradas"),
        (4, "Nado", "Técnica", 60, "{nado_z2}", "Técnica y velocidad"),
        (4, "Carrera", "Suave", 45, "{run_z2}", "Regenerativo"),
        (5, "Bici", "Largo con 3×12'", 210, "{z3}", "Dentro del rodaje, r6'. Come cada 30'"),
        (5, "Carrera", "Ladrillo", 20, "{run_z2}", "Saliendo de la bici"),
        (6, "Carrera", "Larga", 90, "{run_z2}", "Últimos 15' algo más rápidos"),
    ]),
    "espec": (16 * 60, [
        (0, "Nado", "Suave", 60, "{nado_z2}", "Regenerativo y técnica"),
        (0, "Fuerza", "Mantenimiento", 40, "", "Sin llegar al fallo"),
        (1, "Bici", "2×25' a ritmo", 120, "{race_w}", "Sin salir de los acoples"),
        (1, "Carrera", "Ladrillo", 20, "{race_run}", "A ritmo de carrera"),
        (2, "Carrera", "6×1 km a ritmo", 75, "{race_run}", "r2' entre repeticiones"),
        (2, "Nado", "Ritmo de carrera", 60, "{nado_race}", "4×400 al ritmo del día"),
        (3, "Bici", "Rodaje Z2", 90, "{z2}", "Suave, piernas frescas para el sábado"),
        (3, "Nado", "Aguas abiertas", 60, "{nado_race}", "Salidas, giros de boya y orientación"),
        (4, "Nado", "Regenerativo", 45, "{nado_z2}", "Opcional: si estás cansado, descansa"),
        (5, "Bici", "Ladrillo: 90 km", 225, "{race_w}", "Nutrición exacta de carrera. Transición cronometrada"),
        (5, "Carrera", "Ladrillo a ritmo", 40, "{race_run}", "Saliendo de T2 en frío"),
        (6, "Carrera", "Larga", 100, "{run_z2}", "Últimos 20' a ritmo de carrera"),
    ]),
    "test": (11 * 60, [
        (0, "Nado", "Test de CSS", 60, "", "Calentar, 400 m a tope, descanso 5', 200 m a tope. CSS = (t400−t200)÷2"),
        (0, "Fuerza", "Movilidad", 30, "", "Suave, sin cargar"),
        (1, "Bici", "Test de FTP", 75, "", "20' a tope tras calentar. FTP = media × 0,95"),
        (2, "Carrera", "Test de 30'", 60, "", "30' contrarreloj. El ritmo medio es tu umbral"),
        (3, "Bici", "Rodaje Z2", 90, "{z2}", "Suave, asimilando los tests"),
        (3, "Nado", "Técnica", 45, "{nado_z2}", "Grábate: este vídeo es tu punto de partida"),
        (4, "Nado", "Suave", 45, "{nado_z2}", "Regenerativo"),
        (5, "Bici", "Rodaje largo", 135, "{z2}", "En acoples, ajustando la posición"),
        (6, "Carrera", "Larga", 60, "{run_z2}", "Ritmo plano"),
    ]),
    "taper": (11 * 60, [
        (0, "Nado", "Suave", 45, "{nado_z2}", "Técnica"),
        (0, "Fuerza", "Movilidad", 30, "", "Sin cargas"),
        (1, "Bici", "3×10' a ritmo", 75, "{race_w}", "Series cortas, ritmo intacto"),
        (2, "Carrera", "4×800 m", 50, "{run_tempo}", "r2'"),
        (2, "Nado", "Suave", 45, "{nado_z2}", ""),
        (3, "Bici", "Rodaje Z2 + transiciones", 90, "{z2}", "Repasa la secuencia completa de T1 y T2"),
        (4, "Nado", "Suave", 45, "{nado_z2}", ""),
        (4, "Carrera", "Suave", 30, "{run_z2}", ""),
        (5, "Bici", "2×15' a ritmo", 120, "{race_w}", "+ 20' de ladrillo"),
        (6, "Carrera", "Larga corta", 70, "{run_z2}", "20' a ritmo de carrera al final"),
    ]),
    "carrera": (6 * 60, [
        (0, "Descanso", "Descanso total", 0, "", "Nada. En serio"),
        (1, "Bici", "4×3' a ritmo", 45, "{race_w}", "Activación"),
        (2, "Carrera", "5×1' a ritmo", 30, "{race_run}", "Piernas despiertas"),
        (3, "Nado", "Suave", 30, "{nado_z2}", "Viaje y registro"),
        (4, "Bici", "3×2' a ritmo", 30, "{race_w}", "Revisión de material"),
        (5, "Carrera", "Activación", 20, "{race_run}", "4×20\" a ritmo. Piernas en alto el resto del día"),
        (6, "Carrera", "IRONMAN 70.3", 0, "", "Objetivo 5:13. Bici a ritmo, carrera a ritmo, sin heroicidades"),
    ]),
}


def parse_pace(t: str) -> int:
    m, sec = t.replace(".", ":").split(":")
    return int(m) * 60 + int(sec)


def fmt_pace(s: float) -> str:
    s = round(s)
    return f"{s // 60}:{s % 60:02d}"


def objetivos(ftp: int, css: int, umbral: int) -> dict[str, str]:
    """Traduce tus tests a los objetivos que aparecen en cada sesión."""
    w = lambda a, b: f"{round(ftp * a)}–{round(ftp * b)} W"
    r = lambda a, b: f"{fmt_pace(umbral + a)}–{fmt_pace(umbral + b)}/km"
    n = lambda a, b: f"{fmt_pace(css + a)}–{fmt_pace(css + b)}/100 m"
    return {
        "z2": w(0.56, 0.75), "z3": w(0.76, 0.90), "tempo": w(0.85, 0.92),
        "race_w": w(0.75, 0.80),
        "run_z2": r(45, 75), "run_tempo": r(15, 30), "race_run": r(26, 36),
        "nado_z2": n(6, 12), "nado_umbral": n(-1, 1), "nado_vo2": n(-6, -3),
        "nado_race": n(2, 5),
    }


def sesiones(ftp: int, css: int, umbral: int, peso: float = 90.0) -> list[dict]:
    obj = objetivos(ftp, css, umbral)
    pesos = pesos_objetivo(peso)
    filas = []
    for num, bloque, horas, plantilla, foco in SEMANAS:
        base_min, ses = PLANTILLAS[plantilla]
        factor = (horas * 60) / base_min
        lunes = INICIO + timedelta(weeks=num - 1)
        for dia, disc, titulo, minutos, marca, desc in ses:
            dur = round(minutos * factor / 5) * 5 if minutos else 0
            if minutos and dur < 15:
                dur = 15
            filas.append({
                "fecha": (lunes + timedelta(days=dia)).isoformat(),
                "semana": num,
                "bloque": bloque,
                "dia": DIAS[dia],
                "disciplina": disc,
                "sesion": titulo,
                "minutos": dur,
                "objetivo": marca.format(**obj) if marca else "",
                "descripcion": desc,
                "foco_semana": foco,
                "peso_objetivo": pesos[num],
            })
    return filas


def escribir_csv(filas: list[dict], ruta: Path) -> None:
    with ruta.open("w", newline="", encoding="utf-8") as f:
        campos = ["fecha", "semana", "bloque", "dia", "disciplina", "sesion",
                  "minutos", "objetivo", "descripcion", "foco_semana", "peso_objetivo"]
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


ICONO = {"Nado": "🏊", "Bici": "🚴", "Carrera": "🏃", "Fuerza": "🏋️", "Descanso": "😴"}


def escribir_ics(filas: list[dict], ruta: Path) -> None:
    """Calendario importable en Google Calendar, Apple, Outlook y similares."""
    sello = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//find-skill//plan 70.3//ES",
           "CALSCALE:GREGORIAN", "X-WR-CALNAME:Plan 70.3 · camino al 4:04"]
    # la sesión más larga del día va por la tarde, que es cuando entrenas;
    # la secundaria por la mañana. Los ladrillos son la excepción: van pegados
    # a la bici, porque salir a correr en frío no entrena lo mismo.
    pesados: set[str] = set()
    por_dia: dict[str, list[int]] = {}
    for i, f in enumerate(filas):
        if f["minutos"]:
            por_dia.setdefault(f["fecha"], []).append(i)

    inicios: dict[int, datetime] = {}
    for fecha, indices in por_dia.items():
        dia = datetime.fromisoformat(fecha)
        # un ladrillo es la CARRERA que sigue a la bici, no la bici en sí
        ladrillos = [j for j in indices
                     if filas[j]["disciplina"] == "Carrera" and "Ladrillo" in filas[j]["sesion"]]
        resto = [j for j in indices if j not in ladrillos]
        principal = max(resto or indices, key=lambda j: filas[j]["minutos"])

        # entre semana la principal va por la tarde; el fin de semana, por la
        # mañana, porque un rodaje de 3:45 no cabe después de comer
        finde = dia.weekday() >= 5
        inicios[principal] = dia.replace(hour=8 if finde else 18, minute=0)
        fin_principal = inicios[principal] + timedelta(minutes=filas[principal]["minutos"])
        for j in ladrillos:                                  # justo al bajar de la bici
            inicios[j] = fin_principal + timedelta(minutes=5)
            fin_principal = inicios[j] + timedelta(minutes=filas[j]["minutos"] + 5)
        for j in resto:                                      # la segunda sesión
            if j != principal:
                inicios[j] = dia.replace(hour=17, minute=0) if finde \
                    else dia.replace(hour=6, minute=30)

    for i, f in enumerate(filas):
        if not f["minutos"]:
            continue
        ini = inicios[i]
        fin = ini + timedelta(minutes=f["minutos"])
        titulo = f"{ICONO.get(f['disciplina'], '')} {f['disciplina']} · {f['sesion']}"
        if f["objetivo"]:
            titulo += f" ({f['objetivo']})"
        cuerpo = f"Semana {f['semana']} · {f['bloque']}\\n{f['descripcion']}"
        if f["objetivo"]:
            cuerpo += f"\\nObjetivo: {f['objetivo']}"
        if f["dia"] == "Lun" and f["fecha"] not in pesados:
            pesados.add(f["fecha"])
            pesaje = datetime.fromisoformat(f["fecha"]).replace(hour=7, minute=0)
            out += [
                "BEGIN:VEVENT",
                f"UID:plan703-peso-{f['semana']}@find-skill",
                f"DTSTAMP:{sello}",
                f"DTSTART:{pesaje.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{(pesaje + timedelta(minutes=10)).strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:⚖️ Control · objetivo {f['peso_objetivo']:.1f} kg".replace(".", ","),
                "DESCRIPTION:En ayunas y sin ropa. Mide también masa muscular: "
                "si baja de 38\\,6 kg\\, afloja el déficit.",
                "END:VEVENT",
            ]
        out += [
            "BEGIN:VEVENT",
            f"UID:plan703-{i}@find-skill",
            f"DTSTAMP:{sello}",
            f"DTSTART:{ini.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{fin.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{titulo}",
            f"DESCRIPTION:{cuerpo}",
            "END:VEVENT",
        ]
    out.append("END:VCALENDAR")
    ruta.write_text("\r\n".join(out) + "\r\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera el calendario del plan de 25 semanas.")
    ap.add_argument("--ftp", type=int, default=223, help="FTP en vatios (test de 20' × 0,95)")
    ap.add_argument("--css", default="2:20", help="CSS de nado por 100 m")
    ap.add_argument("--umbral", default="5:30", help="Ritmo umbral de carrera por km")
    ap.add_argument("--peso", type=float, default=90, help="Peso corporal actual en kg")
    ap.add_argument("--salida", default=".", help="Carpeta donde escribir los ficheros")
    a = ap.parse_args()

    filas = sesiones(a.ftp, parse_pace(a.css), parse_pace(a.umbral), a.peso)
    destino = Path(a.salida)
    destino.mkdir(parents=True, exist_ok=True)
    escribir_csv(filas, destino / "plan-70.3.csv")
    escribir_ics(filas, destino / "plan-70.3.ics")

    horas = sum(f["minutos"] for f in filas) / 60
    fuerza = sum(1 for f in filas if f["disciplina"] == "Fuerza")
    print(f"{len(filas)} sesiones · {horas:.0f} h · {SEMANAS[0][0]}–{SEMANAS[-1][0]} semanas")
    print(f"  fuerza: {fuerza} sesiones en 25 semanas ({fuerza / 25:.1f} por semana)")
    print(f"  peso: {a.peso:.0f} kg -> {filas[-1]['peso_objetivo']:.1f} kg el día de carrera")
    print(f"  {destino / 'plan-70.3.csv'}")
    print(f"  {destino / 'plan-70.3.ics'}")


if __name__ == "__main__":
    main()
