"""Mando todo-en-uno. Corre en TU PC y reemplaza a Colab mientras juegas.

    giroscopio (Mongo) -> θ' = ω(t) con trapecio -> histéresis -> tecla

    pip install pymongo pynput python-dotenv numpy
    python mando_local_todo.py

Ponlo en la misma carpeta que main1.py (usa el mismo .env con MONGODB_URI).
Colab queda solo para la parte analítica y la exposición.
"""
import os
import time
from datetime import datetime

import numpy as np
from dotenv import load_dotenv
from pymongo import MongoClient
from pynput.keyboard import Controller, Key

load_dotenv()
URI = os.getenv("MONGODB_URI") or "PEGA_TU_URI_DE_MONGODB_ATLAS"

# ---------------- Parámetros (los mismos del cuaderno) ----------------
CAMPOS = ("gy", "gx")        # gy: ARRIBA/ABAJO | gx: IZQUIERDA/DERECHA
SIGNO = np.array([1.0, -1.0]) # -1 en el eje que salga invertido
T_CAL = 2.0
CAL_MAX_STD = 0.10
UMBRAL_W = 0.05
T_REPOSO = 0.6
TH_ON = 25.0
TH_OFF = 10.0
COOLDOWN = 0.35
T_REARME = 0.25              # s quieto tras un comando => θ vuelve a 0 y se rearma (None = desactivado)
SONDEO = 0.05                # s entre consultas a Mongo
PULSO = 0.03                 # s que dura cada pulsación
DEBUG = True                 # muestra el ángulo en vivo (una línea que se actualiza sola)

TECLAS = {"ARRIBA": Key.up, "ABAJO": Key.down,
          "IZQUIERDA": Key.left, "DERECHA": Key.right}


# ---------------- Núcleo: θ' = ω(t), regla del trapecio ----------------
def trapecio(acum, f_ant, f_nueva, dt):
    return acum + 0.5 * (f_ant + f_nueva) * dt


def nuevo_integrador():
    return dict(t=None, t0=None, w=np.zeros(2), th=np.zeros(2), buf=[],
                sesgo=np.zeros(2), umbral=np.full(2, UMBRAL_W),
                calibrado=False, t_act=None, estado="calibrando")


def paso(g, t, w_cruda):
    w_cruda = np.asarray(w_cruda, dtype=float) * SIGNO
    if g["t0"] is None:
        g["t0"] = g["t"] = g["t_act"] = t
        g["buf"] = [w_cruda]
        return True
    dt = t - g["t"]
    if dt <= 0:
        return False

    if not g["calibrado"]:                                   # calibración del sesgo
        g["buf"].append(w_cruda)
        g["t"] = t
        if t - g["t0"] >= T_CAL:
            datos = np.array(g["buf"])
            if datos.std(axis=0).max() > CAL_MAX_STD:
                g["estado"], g["t0"], g["buf"] = "recalibrando: deja el celular quieto", t, []
            else:
                g["sesgo"] = datos.mean(axis=0)
                g["umbral"] = np.maximum(UMBRAL_W, 3.0 * datos.std(axis=0))
                g["calibrado"], g["t_act"], g["estado"] = True, t, "listo"
        return True

    w = w_cruda - g["sesgo"]                                 # sin sesgo + zona muerta
    w = np.where(np.abs(w) < g["umbral"], 0.0, w)

    g["th"] = trapecio(g["th"], g["w"], w, dt)               # UNA integración: ω -> θ
    g["w"], g["t"] = w, t

    if np.any(w != 0.0):                                     # re-centrado en reposo
        g["t_act"], g["estado"] = t, "en movimiento"
    elif t - g["t_act"] >= T_REPOSO:
        g["th"] = np.zeros(2)
        g["estado"] = "en reposo"
    return True


def grados(g):
    return np.degrees(g["th"])


class Comandos:
    """Histéresis (disparador de Schmitt): dispara al cruzar TH_ON, rearma bajo TH_OFF."""
    def __init__(self):
        self.activo, self.t_ult = None, 0.0

    def evaluar(self, ang, ahora):
        pitch, roll = ang
        mayor = max(abs(pitch), abs(roll))
        if self.activo is None:
            if mayor >= TH_ON and ahora - self.t_ult >= COOLDOWN:
                if abs(pitch) >= abs(roll):
                    cmd = "ARRIBA" if pitch > 0 else "ABAJO"
                else:
                    cmd = "DERECHA" if roll > 0 else "IZQUIERDA"
                self.activo, self.t_ult = cmd, ahora
                return cmd
        elif mayor < TH_OFF:
            self.activo = None
        return None


g = nuevo_integrador()
clf = Comandos()


def procesar_doc(doc):
    """Procesa un documento de Mongo y devuelve comandos como (tiempo, nombre)."""
    global g
    cmds = []  # Aqui se acumulan los comandos detectados en este documento.
    # Obtiene las muestras de los ejes configurados en CAMPOS, en ese orden.
    listas = [doc.get(c, []) for c in CAMPOS]
    # Combina cada tiempo con su muestra gy y gx correspondiente.
    for t, *w in zip(doc.get("timestamp", []), *listas):
        # Si el tiempo vuelve a cero, comienza una medicion nueva:
        # reinicia el integrador y limpia el comando activo.
        if g["t"] is not None and t < g["t"] - 1.0 and t < 1.0:
            g, clf.activo = nuevo_integrador(), None
        # paso actualiza la calibracion y el angulo; solo se evalua
        # un comando despues de terminar la calibracion.
        if paso(g, t, w) and g["calibrado"]:
            cmd = clf.evaluar(grados(g), t)
            if cmd:
                # Guarda el tiempo y el nombre; main() usara el nombre para pulsar la tecla.
                cmds.append((t, cmd))
            # Si el gesto ya se disparo y la mano esta quieta, recentra el angulo
            # y rearma la deteccion para permitir otro comando.
            elif (T_REARME is not None and clf.activo and t - clf.t_ult >= T_REARME
                  and not np.any(g["w"])):
                g["th"] = np.zeros(2)
                clf.activo = None
    # Devuelve todos los comandos detectados; no los ejecuta aqui.
    return cmds


# ---------------- Bucle principal ----------------
def main():
    # Se conecta a la coleccion donde main1.py guarda las muestras del giroscopio.
    col = MongoClient(URI)["trayectoria_numerica"]["giroscopio"]
    # Controller permite enviar pulsaciones de teclado a la PC.
    teclado = Controller()
    # Empieza desde el documento mas reciente para no procesar datos viejos.
    ult = col.find_one(sort=[("_id", -1)])
    ultimo_id = ult["_id"] if ult else None

    # Instrucciones que se muestran al iniciar el mando.
    print("🎮 Mando listo. Haz clic en la ventana del juego. Ctrl+C para salir.")
    print("   Dale play en el celular y NO lo muevas durante la calibración (~2 s).")
    # Variables usadas para mostrar el estado, diagnosticos y mensajes una sola vez.
    estado_prev = None
    t_diag = 0.0
    lotes = 0
    avisado = False
    while True:
        # Busca solo documentos nuevos, ordenados desde el mas antiguo al mas reciente.
        filtro = {"_id": {"$gt": ultimo_id}} if ultimo_id else {}
        for doc in col.find(filtro).sort("_id", 1):
            # Avanza el marcador para que el mismo documento no se procese otra vez.
            ultimo_id = doc["_id"]
            lotes += 1
            # Calcula cuanto tardo en llegar el lote, usando el reloj de esta PC.
            try:
                edad = (datetime.now() - doc["recibido_en"]).total_seconds()
            except Exception:
                edad = float("nan")
            # Procesa las muestras; por cada comando detectado, pulsa y suelta su tecla.
            for t, cmd in procesar_doc(doc):
                teclado.press(TECLAS[cmd])
                time.sleep(PULSO)
                teclado.release(TECLAS[cmd])
                print("\r" + f"→ {cmd:<9}  (lote llegó hace {edad:.2f} s)".ljust(100))
        # Muestra cambios importantes en el proceso de calibracion.
        est = g["estado"]
        if lotes > 0 and est != estado_prev and (est.startswith(("calibrando", "recalibrando")) or est == "listo"):
            print({"listo": "🟢 LISTO: ya puedes mover el celular"}.get(est, f"🔴 {est}"))
            estado_prev = est
        # Si aun no llegaron documentos, avisa una sola vez que esta esperando.
        if lotes == 0:
            if not avisado:
                print("⚪ Esperando datos del celular... (dale play en Phyphox)")
                avisado = True
        # Muestra el angulo y estado periodicamente mientras llegan datos.
        elif DEBUG and time.monotonic() - t_diag > 0.3:
            t_diag = time.monotonic()
            p, r = grados(g)
            bloq = f" | {clf.activo}" if clf.activo else ""
            linea = f"lotes {lotes} | ↕{p:+6.1f}° ↔{r:+6.1f}° | {g['estado'].split(':')[0]}{bloq}"
            print(linea[:72].ljust(72), end="\r", flush=True)
        # Espera antes de volver a consultar Mongo para no consultar continuamente.
        time.sleep(SONDEO)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Detenido.")