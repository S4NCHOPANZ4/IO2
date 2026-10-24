"""Constantes del juego. Todo lo ajustable vive aquí."""

HP_INICIAL = 100
BONO_MAX = 10                       # bono de velocidad máximo (+10 de daño)
DIFICULTADES = {                    # segundos por pregunta y daño base
    "facil":   {"tiempo": 10, "dano": 10},
    "media":   {"tiempo": 15, "dano": 15},
    "dificil": {"tiempo": 20, "dano": 20},
}
ORDEN_DIFICULTAD = ["facil", "facil", "media", "media", "dificil"]  # 5 rondas

MAX_LOBBY = 11                      # jugadores máximos en el lobby
CUENTA_REGRESIVA = 3                # segundos antes de la primera pregunta
PAUSA_RESULTADO = 3                 # segundos entre rondas
TOLERANCIA = 0.5                    # margen por latencia al cerrar la ronda
GRACIA_DESCONEXION = 30             # segundos para volver antes de perder
SESION_INACTIVA = 600               # segundos para borrar sesiones desconectadas
MAX_INTENTOS_RECONEXION = 10        # por conexión
ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O/1/I
