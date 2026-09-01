# find-skill

A collection of scripts and utilities to help discover and practice new skills.

## Entrenamiento de ironías

Entrenador interactivo de ironía en español: 36 ejercicios en tres modos
—**reconocer**, **interpretar** y **producir**— con explicación en cada
respuesta, tres niveles de dificultad y repaso de lo que fallaste.

```bash
python3 -m ironias                       # sesión mixta de 10 ejercicios
python3 -m ironias -n 5 -m reconocer     # solo detección, 5 ejercicios
python3 -m ironias --nivel 3             # únicamente los difíciles
python3 -m ironias --tipo dramatica      # un solo tipo de ironía
python3 -m ironias --repaso              # prioriza lo que fallaste
python3 -m ironias --stats               # progreso acumulado
python3 -m ironias --listar              # modos, niveles y tipos disponibles
```

Durante la sesión: escribe la letra de tu respuesta, `pista` para una ayuda
(no penaliza) o `salir` para terminar y ver el informe.

**Modos**

| Modo | Qué entrena | Ejemplo de ejercicio |
|---|---|---|
| `reconocer` | Detectar si hay ironía y de qué tipo | Los bomberos queman su propio patio en una barbacoa → ironía situacional |
| `interpretar` | Traducir lo dicho a lo que se quiere decir | «Tómate el tiempo que necesites» tras tres recordatorios → presión |
| `producir` | Escribir ironía tú, con criterios y modelos | Reescribir una crítica hostil como ironía suave |

El banco incluye **ejercicios de control sin ironía** (hipérbole, cinismo,
elogio sincero) para que entrenar no consista en decir «sí» a todo.

**Progreso.** Se guarda en `~/.find-skill/ironias-progreso.json` (cambia la ruta
con `--progreso` o la variable `IRONIAS_PROGRESO`; `--sin-guardar` lo desactiva y
`--reiniciar` lo borra). `--repaso` usa ese historial para sacar primero los
ejercicios que más fallas.

**Teoría.** Guía breve de tipos, mecanismos y usos en
[`ironias/GUIA.md`](ironias/GUIA.md).

**Requisitos.** Python 3.10+ y nada más: solo biblioteca estándar.

### Tests

```bash
python3 -m unittest discover -s tests
```

### Añadir ejercicios

Edita `ironias/data/ejercicios.json`. Cada ejercicio necesita `id`, `modo`,
`nivel`, `tipo`, `contexto` y `explicacion`; los de `reconocer`/`interpretar`
añaden `opciones` y `respuesta` (índice), y los de `producir`, `consigna`,
`criterios` y `ejemplos`. El banco se valida al cargarse, así que un error de
formato se ve al instante.

## Usage

Clone the repository and explore the available tools.

## Contributing

Contributions are welcome! Please open a pull request with your changes.
