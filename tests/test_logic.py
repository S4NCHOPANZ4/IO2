from game.cola import Cola
from game.match import Partida, calcular_dano
from game.questions import cargar, elegir
from config import ORDEN_DIFICULTAD


def test_banco_con_feedback():
    for q in cargar():
        assert len(q["opciones"]) == 4 and 0 <= q["correcta"] <= 3
        assert q["dificultad"] in ("facil", "media", "dificil")
        assert q["feedback"].strip(), f"falta feedback en la pregunta {q['id']}"


def partida_demo():
    return Partida("a", "b", elegir(cargar()))


def test_dano_base_y_bono():
    assert calcular_dano("media", 0) == 15            # sin bono
    assert calcular_dano("media", 9) == 21            # ejemplo del plan: 15 + 6
    assert calcular_dano("facil", 10) == 20           # máximo fácil
    assert calcular_dano("dificil", 20) == 30         # máximo difícil
    assert calcular_dano("dificil", -5) == 20         # tiempo negativo no resta


def test_seleccion_sin_repetir_y_en_orden():
    qs = elegir(cargar())
    assert [q["dificultad"] for q in qs] == ORDEN_DIFICULTAD
    assert len({q["id"] for q in qs}) == 5


def test_ronda_simultanea_y_primera_respuesta():
    p = partida_demo()
    q = p.iniciar_ronda()
    assert p.responder("a", q["correcta"])
    assert not p.responder("a", 0)                    # segunda respuesta ignorada
    assert p.responder("b", (q["correcta"] + 1) % 4)  # incorrecta
    res = p.resolver()
    assert res["a"]["correcto"] and res["a"]["dano"] >= 10
    assert res["b"]["dano"] == 0
    assert p.hp["b"] == 100 - res["a"]["dano"] and p.hp["a"] == 100


def test_sin_respuesta_no_hace_dano():
    p = partida_demo()
    p.iniciar_ronda()
    res = p.resolver()
    assert not res["a"]["respondio"] and p.hp == {"a": 100, "b": 100}


def test_resultados_finales():
    p = partida_demo()
    p.hp = {"a": 0, "b": 40}
    assert p.resultado_final() == ("b", "ko")
    p.hp = {"a": 0, "b": 0}
    assert p.resultado_final() == (None, "doble_ko")
    p.hp = {"a": 60, "b": 40}
    assert p.resultado_final() == ("a", "hp")
    p.hp = {"a": 50, "b": 50}
    p.tiempo_total = {"a": 8.0, "b": 5.0}
    assert p.resultado_final() == ("b", "desempate")
    p.tiempo_total = {"a": 0.0, "b": 0.0}
    assert p.resultado_final() == (None, "empate")
    p.abandono = "a"
    assert p.resultado_final() == ("b", "abandono")


def test_cola_empareja_en_orden():
    c = Cola()
    c.agregar("x"); c.agregar("x"); c.agregar("y"); c.agregar("z")
    assert c.sacar_par() == ("x", "y")
    assert c.sacar_par() is None and len(c) == 1
    c.quitar("z")
    assert len(c) == 0
