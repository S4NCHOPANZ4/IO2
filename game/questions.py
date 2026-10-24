"""Carga del banco de preguntas y selección para una partida."""
import json
import random
from pathlib import Path

from config import ORDEN_DIFICULTAD

RUTA = Path(__file__).resolve().parent.parent / "data" / "preguntas.json"


def cargar(ruta=RUTA):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def elegir(banco):
    """Una pregunta por ronda según ORDEN_DIFICULTAD, sin repetir."""
    por_dif = {}
    for p in banco:
        por_dif.setdefault(p["dificultad"], []).append(p)
    elegidas, usadas = [], set()
    for dif in ORDEN_DIFICULTAD:
        candidatas = [p for p in por_dif.get(dif, []) if p["id"] not in usadas]
        p = random.choice(candidatas)
        usadas.add(p["id"])
        elegidas.append(p)
    return elegidas
