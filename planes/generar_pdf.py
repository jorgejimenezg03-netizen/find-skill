#!/usr/bin/env python3
"""Convierte el plan HTML en un PDF imprimible con anexo de sesiones.

Toma el documento del plan, le añade un anexo con las 279 sesiones del CSV,
incrusta las tipografías (Chromium no sale a internet en este entorno) y lo
imprime a PDF en A4.

    python3 planes/generar_pdf.py --salida plan-70.3-monterrey.pdf

Necesita Chromium. Si no está en la ruta por defecto, pásala con --chromium.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).parent
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
FUENTES = [
    "https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700"
    "&family=IBM+Plex+Mono:wght@400;600",
    # Source Serif 4 es variable y Chromium la descarta: se usa la estática
    "https://fonts.googleapis.com/css2?family=Source+Serif+Pro:ital,wght@0,400;0,600;1,400",
]
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

CSS_IMPRESION = """
@page { size: A4; margin: 15mm 12mm 14mm; }
:root { color-scheme: light; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { padding: 0 !important; font-size: 10.5pt; background: var(--card) !important; }
header.hero { background: transparent; border-bottom: 0; padding: 0 0 1.2rem;
  margin-bottom: 1.5rem; break-after: page; }
header.hero .factbar { border-top: 1px solid var(--rule); padding-top: 1.2rem; }
.wrap { max-width: none; padding: 0; }
.hero h1 { font-size: 46pt; } .hero .lede { font-size: 12pt; }
section { break-before: page; margin-bottom: 1.5rem; }
h2 { font-size: 20pt; } h3 { font-size: 13pt; margin-top: 1.2rem; } h4 { font-size: 11.5pt; }
h2, h3, h4, .shead { break-after: avoid; }
table { font-size: 8.6pt; } th, td { padding: .28rem .4rem; }
.tw { overflow: visible !important; }
tr { break-inside: avoid; } thead { display: table-header-group; }
caption { font-size: 8.2pt; }
.keys { display: block; } .key { break-inside: avoid; margin-bottom: .6rem; }
.tabs { display: none !important; }
.panel { margin-bottom: 1rem; border-radius: 0; }
.panel[hidden] { display: block !important; }
.calib-in, .proj, .gate, .callout { break-inside: avoid; }
.load { height: 120px; }
footer { margin-top: 1.5rem; font-size: 9pt; }
.anexo table.anx { font-size: 7.6pt; width: 100%; margin: .2rem 0 .8rem; }
.anexo table.anx td, .anexo table.anx th { padding: .2rem .35rem; vertical-align: top; }
.anexo h3.sem { font-size: 11.5pt; margin: .9rem 0 .1rem;
  border-top: 1.5px solid var(--ink); padding-top: .3rem; }
.anexo h3.sem .peso { font-family: var(--mono); font-size: 8.5pt; font-weight: 400;
  color: var(--muted); float: right; }
.anexo p.foco { font-size: 8.6pt; color: var(--muted); margin: 0 0 .3rem; }
.anexo td.d { font-family: var(--mono); white-space: nowrap; width: 8%; }
.anexo td.n { font-family: var(--mono); white-space: nowrap; }
.anexo td.como { font-size: 7.3pt; line-height: 1.35; color: var(--muted); }
.anexo .disc { font-family: var(--display); font-weight: 700; font-size: 7pt;
  display: inline-block; width: 12px; text-align: center;
  border: 1px solid var(--rule); border-radius: 2px; }
"""

# Las pestañas se despliegan todas: en papel no hay dónde pulsar
JS_IMPRESION = """
document.addEventListener("DOMContentLoaded", function(){
  document.documentElement.setAttribute("data-theme", "light");
  document.querySelectorAll(".panel").forEach(function(p){
    p.hidden = false;
    var t = document.getElementById(p.getAttribute("aria-labelledby"));
    if (t) {
      var h = document.createElement("h3");
      h.textContent = t.textContent;
      h.style.margin = "1.2rem 0 .3rem";
      p.parentNode.insertBefore(h, p);
    }
  });
});
"""

ICONO = {"Nado": "N", "Bici": "B", "Carrera": "C", "Fuerza": "F", "Descanso": "—"}


def anexo(ruta_csv: Path) -> str:
    filas = list(csv.DictReader(ruta_csv.open(encoding="utf-8")))
    por_sem: dict[int, list[dict]] = defaultdict(list)
    for f in filas:
        por_sem[int(f["semana"])].append(f)

    out = [f'<section class="anexo"><div class="shead">'
           f'<h2>Anexo · las {len(filas)} sesiones</h2><span class="n">A</span></div>',
           '<div class="col"><p>El plan completo, sesión a sesión. Los objetivos están '
           'calculados con los valores de partida; tras cada test, regenera el calendario '
           'con tus números reales y esta tabla cambia entera.</p></div>']
    for n in sorted(por_sem):
        ses = por_sem[n]
        horas = sum(int(f["minutos"]) for f in ses) / 60
        cab = ses[0]
        out.append(f'<h3 class="sem">Semana {n} · {html.escape(cab["bloque"])} · {horas:.1f} h'
                   f'<span class="peso">objetivo {cab["peso_objetivo"]} kg</span></h3>')
        out.append(f'<p class="foco">{html.escape(cab["foco_semana"])}</p>')
        out.append('<table class="anx"><thead><tr><th>Día</th><th>Sesión</th>'
                   '<th class="n">Min</th><th class="n">Objetivo</th><th>Cómo</th>'
                   '</tr></thead><tbody>')
        for f in ses:
            out.append(
                f'<tr><td class="d">{f["dia"]} {f["fecha"][8:]}/{f["fecha"][5:7]}</td>'
                f'<td><span class="disc">{ICONO.get(f["disciplina"], "")}</span> '
                f'{html.escape(f["sesion"])}</td>'
                f'<td class="n">{f["minutos"] if int(f["minutos"]) else "—"}</td>'
                f'<td class="n">{html.escape(f["objetivo"])}</td>'
                f'<td class="como">{html.escape(f["descripcion"])}</td></tr>')
        out.append("</tbody></table>")
    out.append("</section>")
    return "\n".join(out)


def fuentes_incrustadas() -> str:
    """Descarga las tipografías y las deja como data URI, subconjunto latino."""
    css_total = []
    for url in FUENTES:
        r = subprocess.run(["curl", "-sS", "--max-time", "30", "-A", UA, url],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  aviso: no se pudo descargar {url[:60]}…; se usarán las de respaldo")
            continue
        css = "".join(b for b in re.split(r"(?=/\* [a-z-]+ \*/)", r.stdout)
                      if re.match(r"/\* latin(-ext)? \*/", b.strip()))
        for u in sorted(set(re.findall(r"url\((https://fonts\.gstatic\.com[^)]+)\)", css))):
            f = subprocess.run(["curl", "-sS", "--max-time", "30", "-o", "-", u],
                               capture_output=True)
            if f.stdout[:4] == b"wOF2":
                css = css.replace(u, "data:font/woff2;base64,"
                                  + base64.b64encode(f.stdout).decode())
        css_total.append(css.replace("'Source Serif Pro'", "'Source Serif 4'"))
    return "".join(css_total)


def construir(plan: Path, csv_sesiones: Path) -> str:
    frag = plan.read_text(encoding="utf-8")
    corte = frag.index("</style>") + len("</style>")
    cabeza, cuerpo = frag[:corte], frag[corte:]
    # fuera el enlace a Google Fonts: se sustituye por las incrustadas
    cabeza = re.sub(r'<link rel="(preconnect|stylesheet)"[^>]*fonts\.(googleapis|gstatic)[^>]*>',
                    "", cabeza)
    cuerpo = cuerpo.replace('<footer class="col">',
                            anexo(csv_sesiones) + '\n<footer class="col">', 1)
    return ("<!doctype html><html lang=\"es\" data-theme=\"light\"><head>"
            "<meta charset=\"utf-8\">"
            f"{cabeza}<style>{fuentes_incrustadas()}</style>"
            f"<style>{CSS_IMPRESION}</style><script>{JS_IMPRESION}</script>"
            f"</head><body>{cuerpo}</body></html>")


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera el PDF del plan.")
    ap.add_argument("--plan", default=str(RAIZ / "ironman-70.3-camino-al-4-04.html"))
    ap.add_argument("--csv", default="plan-70.3.csv", help="CSV de sesiones")
    ap.add_argument("--salida", default="plan-70.3-monterrey.pdf")
    ap.add_argument("--chromium", default=CHROMIUM)
    a = ap.parse_args()

    doc = construir(Path(a.plan), Path(a.csv))
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as t:
        t.write(doc)
        temporal = Path(t.name)

    salida = Path(a.salida).resolve()
    r = subprocess.run([
        a.chromium, "--headless", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
        "--virtual-time-budget=25000", "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={salida}", "--no-pdf-header-footer", temporal.as_uri(),
    ], capture_output=True, text=True)
    temporal.unlink()
    if not salida.exists():
        raise SystemExit("Chromium no generó el PDF:\n" + r.stderr[-800:])
    print(f"{salida} · {salida.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
