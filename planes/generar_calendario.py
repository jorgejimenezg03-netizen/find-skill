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
        (0, "Nado", "Técnica", 60, "{nado_z2}", "Cal 300 m suave | 8×50 con tabla (patada, cadera alta) · 8×50 con pull-boy · 6×25 puño cerrado · 4×50 punto muerto | Calma 200 m"),
        (0, "Fuerza", "Fuerza máxima", 45, "", "Sesión A: sentadilla 4×5 al 80-85 % r3' · peso muerto rumano 3×6 r2:30 · zancada búlgara 3×8/pierna · gemelo de pie 3×12 · plancha lateral 3×40\". RIR 2, nunca al fallo"),
        (1, "Bici", "Rodaje Z2", 90, "{z2}", "Rodaje continuo en Z2, los últimos 30' sin salir de acoples. Debes poder hablar en frases completas todo el rato"),
        (1, "Carrera", "Suave", 35, "{run_z2}", "Trote suave en Z2. Si no puedes conversar, vas rápido. Sube el tiempo máximo un 10 % por semana"),
        (2, "Nado", "Series cortas", 60, "{nado_umbral}", "Cal 400 m progresivo | 16×50 a ritmo umbral r15\" | Calma 200 m. Grábate de frente y de lado cada tres semanas"),
        (2, "Carrera", "Suave + zancadas", 50, "{run_z2}", "Z2 continuo + 6×20\" de zancadas al final (rápido y suelto, no sprint), r40\" andando"),
        (3, "Bici", "Rodaje Z2", 105, "{z2}", "Rodaje en Z2 entero en acoples. Si la espalda protesta, sal 1' cada 15' y vuelve: se adapta en tres semanas"),
        (3, "Fuerza", "Fuerza máxima", 45, "", "Sesión B: dominadas 4×6 · remo con barra 4×8 · hip thrust 3×8 · press militar 3×8 · pallof press 3×10/lado · plancha 3×45\". RIR 2, nunca al fallo"),
        (4, "Nado", "Velocidad", 60, "{nado_vo2}", "Cal 400 m | 8×50 técnica · 16×25 máximos r20\" | Calma 200 m. Series cortas y rápidas: enseñan a mover el brazo rápido sin perder la técnica"),
        (5, "Bici", "Rodaje largo", 165, "{z2}", "Rodaje largo en Z2, llano y en acoples. Bebe cada 15' y come cada 30'. Es la sesión que construye el motor"),
        (5, "Carrera", "Ladrillo", 15, "{run_z2}", "Ladrillo corto: transición de 60\" cronometrada, luego 5' a cadencia alta (88-92 pasos/min) y el resto suelto"),
        (6, "Carrera", "Larga", 75, "{run_z2}", "Larga en Z2 a ritmo constante. Nada de acelerar cuesta abajo: el objetivo es sostener un ritmo aburrido"),
    ]),
    "constr": (16 * 60, [
        (0, "Nado", "Técnica", 60, "{nado_z2}", "Cal 300 m | 8×50 con tabla · 8×50 con pull-boy · 6×25 puño cerrado · 4×50 punto muerto | Calma 200 m"),
        (0, "Fuerza", "Fuerza máxima", 45, "", "Sesión A: sentadilla 4×5 al 80-85 % r3' · peso muerto rumano 3×6 r2:30 · zancada búlgara 3×8/pierna · gemelo 3×12 · plancha lateral 3×40\". RIR 2, nunca al fallo"),
        (1, "Bici", "Tempo 3×8'", 105, "{tempo}", "Cal 15' Z2 + 3×30\" a 100 rpm | 3×8' en tempo a 85-90 rpm, r4' en Z1 | Calma 10'. Todo en acoples"),
        (1, "Carrera", "Ladrillo", 25, "{run_z2}", "Ladrillo: transición de 60\", 5' a cadencia alta y zancada corta, resto a ritmo de carrera"),
        (2, "Carrera", "Tempo 4×5'", 70, "{run_tempo}", "Cal 15' Z2 + 4×20\" zancadas | 4×5' en tempo, r2' trotando (nunca parado) | Calma 10'"),
        (2, "Nado", "8×100", 60, "{nado_umbral}", "Cal 400 m progresivo | 8×100 a CSS r20\" | Calma 200 m"),
        (3, "Bici", "Rodaje Z2", 120, "{z2}", "Rodaje continuo en Z2, en acoples todo el rato. Día suave entre las dos sesiones de calidad de la semana"),
        (3, "Fuerza", "Fuerza + transiciones", 60, "", "Sesión B: dominadas 4×6 · remo 4×8 · hip thrust 3×8 · press militar 3×8 · pallof 3×10/lado · plancha 3×45\". Luego 20' de transiciones: 10 repeticiones de bajar de la bici, calzarte y salir corriendo, con cronómetro"),
        (4, "Nado", "Técnica", 60, "{nado_z2}", "Cal 300 m | 8×50 técnica · 12×25 rápidos r20\" | Calma 200 m"),
        (4, "Carrera", "Suave", 45, "{run_z2}", "Trote muy suave en Z1-Z2. Si dudas si va lento, va bien"),
        (5, "Bici", "Largo con 3×12'", 210, "{z3}", "Cal 45' en Z2 | 3×12' en tempo dentro del rodaje, r6' rodando en Z2 sin parar | Resto en Z2. Come cada 30'"),
        (5, "Carrera", "Ladrillo", 20, "{run_z2}", "Ladrillo: transición de 60\", 5' a cadencia alta y zancada corta, resto a ritmo de carrera"),
        (6, "Carrera", "Larga", 90, "{run_z2}", "Larga en Z2 con los últimos 15' en tempo. Termina más rápido de lo que empezaste"),
    ]),
    "espec": (16 * 60, [
        (0, "Nado", "Suave", 60, "{nado_z2}", "Cal 300 m | 6×50 técnica suave · 4×100 en Z2 | Calma 200 m. Sesión de recuperación, no de trabajo"),
        (0, "Fuerza", "Mantenimiento", 40, "", "Mantenimiento: sesión A reducida a 2×5 al 80 %, RIR 3. Mantener fuerza, no construirla"),
        (1, "Bici", "2×25' a ritmo", 120, "{race_w}", "Cal 20' Z2 | 2×25' a ritmo de carrera sin salir de acoples ni una vez, r8' | Calma 10'"),
        (1, "Carrera", "Ladrillo", 20, "{race_run}", "Ladrillo a ritmo: transición de 60\", los primeros 5' contenidos y el resto a ritmo de carrera"),
        (2, "Carrera", "6×1 km a ritmo", 75, "{race_run}", "Cal 15' Z2 + 4×20\" zancadas | 6×1000 m a ritmo de carrera, r2' trotando | Calma 10'"),
        (2, "Nado", "Ritmo de carrera", 60, "{nado_race}", "Cal 400 m | 4×400 a ritmo de carrera r30\" | Calma 200 m"),
        (3, "Bici", "Rodaje Z2", 90, "{z2}", "Z2 suave. Esta sesión existe para llegar fresco al ladrillo del sábado: no la conviertas en otra cosa"),
        (3, "Nado", "Aguas abiertas", 60, "{nado_race}", "Cal 400 m | 4×400 con giros de boya, orientando cada 6 brazadas · 2 salidas rápidas de 100 m | Calma 200 m"),
        (4, "Nado", "Regenerativo", 45, "{nado_z2}", "Nado regenerativo suave. Si vienes cargado del jueves, descansa: es la sesión más prescindible de la semana"),
        (5, "Bici", "Ladrillo: 90 km", 225, "{race_w}", "Cal 15' | 90 km en acoples a ritmo de carrera: potencia plana, bebe cada 15', come cada 20'. Últimos 10' a 95 rpm | T2 cronometrada, objetivo bajar de 2:00"),
        (5, "Carrera", "Ladrillo a ritmo", 40, "{race_run}", "Primeros 10' a ritmo objetivo +10 s/km (contenido), 25' a ritmo de carrera con un gel a los 20', últimos 5' libres. Apunta el ritmo de los últimos 10'"),
        (6, "Carrera", "Larga", 100, "{run_z2}", "Larga en Z2 con los últimos 20' a ritmo de carrera. Simula el final del medio maratón"),
    ]),
    "test": (11 * 60, [
        (0, "Nado", "Test de CSS", 60, "", "Cal 600 m suave + 4×50 progresivos | 400 m A TOPE, anota el tiempo · 5' de descanso completo · 200 m A TOPE | Calma 200 m. CSS por 100 m = (t400 − t200) ÷ 2"),
        (0, "Fuerza", "Movilidad", 30, "", "Movilidad de cadera, tobillo y torácica. Sin cargas: esta semana es de medir, no de entrenar"),
        (1, "Bici", "Test de FTP", 75, "", "Cal 20' progresivo + 3×1' fuerte r2' | 5' suave | 20' A TOPE en acoples, empieza conservador y sube desde el minuto 5 | Calma 10'. FTP = potencia media × 0,95"),
        (2, "Carrera", "Test de 30'", 60, "", "Cal 15' Z2 + 4×20\" zancadas | 30' contrarreloj en llano, ritmo sostenible máximo | Calma 10'. Tu umbral es el ritmo medio de los últimos 20'"),
        (3, "Bici", "Rodaje Z2", 90, "{z2}", "Rodaje continuo en Z2 asimilando los tests. Aprovecha para ajustar la altura y el alcance de los acoples"),
        (3, "Nado", "Técnica", 45, "{nado_z2}", "Cal 300 m | 8×50 con tabla · 8×50 con pull-boy | Calma 200 m. Grábate de frente y de lado: este vídeo es tu punto de partida"),
        (4, "Nado", "Suave", 45, "{nado_z2}", "Cal 300 m | 6×50 técnica · 4×100 suaves r20\" | Calma 200 m. Regenerativo tras los tests"),
        (5, "Bici", "Rodaje largo", 135, "{z2}", "Rodaje largo en Z2. Ve alternando 15' en acoples y 5' en manetas: la primera semana la espalda no aguanta seguido, y es normal"),
        (6, "Carrera", "Larga", 60, "{run_z2}", "Larga en Z2 a ritmo constante. Si vienes de correr menos de 1,5 h semanales, recorta a 45' y sube un 10 % por semana"),
    ]),
    "taper": (11 * 60, [
        (0, "Nado", "Suave", 45, "{nado_z2}", "Cal 300 m | 6×50 técnica · 4×50 rápidos r20\" | Calma 200 m"),
        (0, "Fuerza", "Movilidad", 30, "", "Solo movilidad: cadera, tobillo y torácica. En afinado no se levanta peso"),
        (1, "Bici", "3×10' a ritmo", 75, "{race_w}", "Cal 15' Z2 | 3×10' a ritmo de carrera en acoples, r5' | Calma 10'. Menos volumen, mismo ritmo"),
        (2, "Carrera", "4×800 m", 50, "{run_tempo}", "Cal 15' + 4×20\" zancadas | 4×800 m en tempo, r2' trotando | Calma 10'"),
        (2, "Nado", "Suave", 45, "{nado_z2}", ""),
        (3, "Bici", "Rodaje Z2 + transiciones", 90, "{z2}", "70' en Z2 + 20' de transiciones: monta la bolsa como el día de carrera y repite T1 y T2 cinco veces cada una, con cronómetro"),
        (4, "Nado", "Suave", 45, "{nado_z2}", ""),
        (4, "Carrera", "Suave", 30, "{run_z2}", ""),
        (5, "Bici", "2×15' a ritmo", 120, "{race_w}", "Cal 20' | 2×15' a ritmo de carrera en acoples, r10' | 20' de ladrillo corriendo a ritmo. Último ensayo completo"),
        (6, "Carrera", "Larga corta", 70, "{run_z2}", "50' en Z2 + 20' a ritmo de carrera al final. La última larga: no busques nada, solo confirma sensaciones"),
    ]),
    "carrera": (6 * 60, [
        (0, "Descanso", "Descanso total", 0, "", "Nada. En serio"),
        (1, "Bici", "4×3' a ritmo", 45, "{race_w}", "Activación"),
        (2, "Carrera", "5×1' a ritmo", 30, "{race_run}", "Piernas despiertas"),
        (3, "Nado", "Suave", 30, "{nado_z2}", "Viaje y registro"),
        (4, "Bici", "3×2' a ritmo", 30, "{race_w}", "Revisión de material"),
        (5, "Carrera", "Activación", 20, "{race_run}", "4×20\" a ritmo. Piernas en alto el resto del día"),
        (6, "Carrera", "IRONMAN 70.3 MONTERREY", 0, "", "Nado: sal por fuera, sin pelea. Bici: potencia plana en acoples, los 15 primeros minutos por debajo del objetivo. Carrera: los 3 primeros km a ritmo +8 s/km, luego a ritmo. Objetivo 5:03"),
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
    ap.add_argument("--ftp", type=int, default=212, help="FTP en vatios (test de 20' × 0,95)")
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
