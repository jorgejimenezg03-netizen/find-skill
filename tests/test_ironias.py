"""Pruebas del entrenamiento de ironías (solo biblioteca estándar)."""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ironias import banco, cli, progreso as prog  # noqa: E402
from ironias.sesion import Sesion, informe, normalizar_opcion  # noqa: E402


class TestBanco(unittest.TestCase):
    def setUp(self):
        self.ejercicios = banco.cargar()

    def test_el_banco_carga_y_valida(self):
        self.assertGreaterEqual(len(self.ejercicios), 30)

    def test_ids_unicos(self):
        ids = [e.id for e in self.ejercicios]
        self.assertEqual(len(ids), len(set(ids)))

    def test_los_tres_modos_tienen_ejercicios(self):
        for modo in banco.MODOS:
            self.assertTrue(banco.filtrar(self.ejercicios, modo=modo), modo)

    def test_los_tres_niveles_tienen_ejercicios(self):
        for nivel in (1, 2, 3):
            self.assertTrue(banco.filtrar(self.ejercicios, nivel=nivel), nivel)

    def test_opcion_multiple_bien_formada(self):
        for ej in self.ejercicios:
            if ej.es_opcion_multiple:
                self.assertIn(ej.respuesta, range(len(ej.opciones)), ej.id)
                self.assertEqual(len(set(ej.opciones)), len(ej.opciones), ej.id)
            else:
                self.assertTrue(ej.criterios, ej.id)
                self.assertTrue(ej.ejemplos, ej.id)

    def test_hay_controles_sin_ironia(self):
        # Sin no-ejemplos el entrenamiento premia decir "sí, es ironía" siempre.
        self.assertGreaterEqual(len(banco.filtrar(self.ejercicios, tipo="literal")), 3)

    def test_filtrar_combina_criterios(self):
        sel = banco.filtrar(self.ejercicios, modo="reconocer", nivel=1)
        self.assertTrue(sel)
        self.assertTrue(all(e.modo == "reconocer" and e.nivel == 1 for e in sel))

    def test_seleccionar_respeta_el_numero(self):
        self.assertEqual(len(banco.seleccionar(self.ejercicios, 5)), 5)
        self.assertEqual(len(banco.seleccionar(self.ejercicios, 999)), len(self.ejercicios))

    def test_repaso_prioriza_los_fallados(self):
        objetivo = self.ejercicios[-1].id
        historial = {objetivo: {"vistas": 3, "aciertos": 0, "fallos": 3}}
        sel = banco.seleccionar(self.ejercicios, 1, progreso=historial, repaso=True)
        self.assertEqual(sel[0].id, objetivo)

    def test_banco_invalido_da_error_claro(self):
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "malo.json"
            ruta.write_text(json.dumps({"ejercicios": [{"id": "x", "modo": "reconocer"}]}))
            with self.assertRaises(banco.BancoInvalido):
                banco.cargar(ruta)


class TestSesion(unittest.TestCase):
    def _sesion(self, ejercicios, respuestas):
        guion = iter(respuestas)
        salida = []
        sesion = Sesion(
            ejercicios,
            entrada=lambda _prompt: next(guion),
            salida=salida.append,
            color=False,
        )
        return sesion, salida

    def test_normalizar_opcion(self):
        self.assertEqual(normalizar_opcion("a", 3), 0)
        self.assertEqual(normalizar_opcion(" B) ", 3), 1)
        self.assertEqual(normalizar_opcion("3.", 3), 2)
        self.assertIsNone(normalizar_opcion("z", 3))
        self.assertIsNone(normalizar_opcion("9", 3))
        self.assertIsNone(normalizar_opcion("", 3))

    def test_respuesta_correcta_e_incorrecta(self):
        ejercicios = banco.filtrar(banco.cargar(), modo="reconocer")[:1]
        letra = "abcdefg"[ejercicios[0].respuesta]
        sesion, _ = self._sesion(ejercicios, [letra])
        self.assertTrue(sesion.ejecutar()[0].acierto)

        mala = "abcdefg"[(ejercicios[0].respuesta + 1) % len(ejercicios[0].opciones)]
        sesion, _ = self._sesion(ejercicios, [mala])
        self.assertFalse(sesion.ejecutar()[0].acierto)

    def test_pista_no_consume_el_intento(self):
        ejercicios = banco.filtrar(banco.cargar(), modo="reconocer")[:1]
        letra = "abcdefg"[ejercicios[0].respuesta]
        sesion, salida = self._sesion(ejercicios, ["pista", letra])
        resultados = sesion.ejecutar()
        self.assertEqual(len(resultados), 1)
        self.assertIn("Pista", "\n".join(salida))

    def test_entrada_invalida_vuelve_a_preguntar(self):
        ejercicios = banco.filtrar(banco.cargar(), modo="reconocer")[:1]
        letra = "abcdefg"[ejercicios[0].respuesta]
        sesion, _ = self._sesion(ejercicios, ["zzz", "42", letra])
        self.assertTrue(sesion.ejecutar()[0].acierto)

    def test_salir_corta_la_sesion_y_conserva_lo_hecho(self):
        ejercicios = banco.filtrar(banco.cargar(), modo="reconocer")[:3]
        letra = "abcdefg"[ejercicios[0].respuesta]
        sesion, _ = self._sesion(ejercicios, [letra, "salir"])
        self.assertEqual(len(sesion.ejecutar()), 1)

    def test_modo_producir_usa_la_autoevaluacion(self):
        ejercicios = banco.filtrar(banco.cargar(), modo="producir")[:1]
        sesion, salida = self._sesion(ejercicios, ["mi intento irónico", "s"])
        resultados = sesion.ejecutar()
        self.assertTrue(resultados[0].acierto)
        self.assertIn("Criterios", "\n".join(salida))

    def test_informe_desglosa_y_lista_repaso(self):
        ejercicios = banco.filtrar(banco.cargar(), modo="reconocer")[:2]
        buena = "abcdefg"[ejercicios[0].respuesta]
        mala = "abcdefg"[(ejercicios[1].respuesta + 1) % len(ejercicios[1].opciones)]
        sesion, _ = self._sesion(ejercicios, [buena, mala])
        texto = informe(sesion.ejecutar())
        self.assertIn("1/2 (50%)", texto)
        self.assertIn("Por modo", texto)
        self.assertIn(ejercicios[1].id, texto)


class TestProgreso(unittest.TestCase):
    def test_registrar_guardar_y_cargar(self):
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "sub" / "progreso.json"
            datos = prog.registrar({}, "rec-001", acierto=True)
            prog.registrar(datos, "rec-001", acierto=False)
            prog.guardar(datos, ruta)

            recuperado = prog.cargar(ruta)
            self.assertEqual(recuperado["rec-001"]["vistas"], 2)
            self.assertEqual(recuperado["rec-001"]["fallos"], 1)

            resumen = prog.resumen(recuperado)
            self.assertEqual(resumen["respuestas"], 2)
            self.assertEqual(resumen["porcentaje"], 50)

    def test_progreso_corrupto_no_rompe(self):
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "roto.json"
            ruta.write_text("{esto no es json")
            self.assertEqual(prog.cargar(ruta), {})

    def test_progreso_inexistente_es_vacio(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(prog.cargar(Path(tmp) / "nada.json"), {})


class TestCli(unittest.TestCase):
    def test_listar_muestra_modos_y_tipos(self):
        texto = cli.listar(banco.cargar())
        self.assertIn("reconocer", texto)
        self.assertIn("ironía dramática", texto)

    def test_filtros_sin_resultados_devuelve_error(self):
        with TemporaryDirectory() as tmp:
            codigo = cli.main(["--tipo", "inexistente", "--progreso", f"{tmp}/p.json"])
        self.assertEqual(codigo, 1)

    def test_num_invalido_devuelve_error(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(cli.main(["-n", "0", "--progreso", f"{tmp}/p.json"]), 1)

    def test_stats_sin_progreso(self):
        texto = cli.formatear_stats(prog.resumen({}))
        self.assertIn("Todavía no hay progreso", texto)

    def test_reiniciar_vacia_el_fichero(self):
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "p.json"
            prog.guardar({"rec-001": {"vistas": 1, "aciertos": 1, "fallos": 0}}, ruta)
            self.assertEqual(cli.main(["--reiniciar", "--progreso", str(ruta)]), 0)
            self.assertEqual(prog.cargar(ruta), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
