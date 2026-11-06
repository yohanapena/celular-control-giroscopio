from fastapi import FastAPI, Request
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime
import uvicorn

load_dotenv()

app = FastAPI()

# Conexión a MongoDB Atlas
MONGODB_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGODB_URI)

db = client["trayectoria_numerica"]
coleccion = db["acelerometro"]
coleccion_giro = db["giroscopio"]      # NUEVO: datos del giroscopio


@app.post("/acelerometro")
async def recibir_medicion(request: Request):

    datos = await request.json()

    timestamp = datos.get("timestamp", [])
    ax = datos.get("ax", [])
    ay = datos.get("ay", [])
    az = datos.get("az", [])

    print("\n========== MEDICIÓN RECIBIDA ==========")

    print(f"Muestras de tiempo: {len(timestamp)}")
    print(f"Muestras ax:        {len(ax)}")
    print(f"Muestras ay:        {len(ay)}")
    print(f"Muestras az:        {len(az)}")

    if timestamp:
        print(f"Tiempo inicial: {timestamp[0]:.4f} s")
        print(f"Tiempo final:   {timestamp[-1]:.4f} s")

    if ax:
        print(f"Último ax: {ax[-1]:.4f} m/s²")

    if ay:
        print(f"Último ay: {ay[-1]:.4f} m/s²")

    if az:
        print(f"Último az: {az[-1]:.4f} m/s²")

    documento = {
        "timestamp": timestamp,
        "ax": ax,
        "ay": ay,
        "az": az,
        "recibido_en": datetime.now()
    }

    resultado = coleccion.insert_one(documento)

    print(f"Guardado en MongoDB: {resultado.inserted_id}")

    return {
        "estado": "recibido",
        "muestras": len(timestamp)
    }


@app.post("/giroscopio")
async def recibir_giroscopio(request: Request):
    """NUEVO: recibe velocidad angular (rad/s) del giroscopio de Phyphox."""

    datos = await request.json()

    timestamp = datos.get("timestamp", [])
    gx = datos.get("gx", [])
    gy = datos.get("gy", [])
    gz = datos.get("gz", [])

    print(f"[giro] {len(timestamp)} muestras", end="")
    if timestamp:
        print(f" | t = {timestamp[0]:.2f} → {timestamp[-1]:.2f} s", end="")
    if gx and gy:
        print(f" | último gx={gx[-1]:+.3f} gy={gy[-1]:+.3f} rad/s", end="")
    print()

    documento = {
        "timestamp": timestamp,
        "gx": gx,
        "gy": gy,
        "gz": gz,
        "recibido_en": datetime.now()
    }

    coleccion_giro.insert_one(documento)

    return {
        "estado": "recibido",
        "muestras": len(timestamp)
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
