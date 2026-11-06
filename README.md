# API de acelerómetro y giroscopio

API para recibir mediciones enviadas desde Phyphox y guardarlas en MongoDB Atlas. Incluye también un programa local que interpreta los datos del giroscopio y los convierte en pulsaciones de teclas.

## Requisitos

- Python 3
- Una base de datos MongoDB accesible desde el equipo
- Phyphox para enviar mediciones desde el celular

## Instalación

Abre una terminal en esta carpeta y crea un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instala las dependencias de la API:

```powershell
python -m pip install fastapi uvicorn pymongo python-dotenv
```

Para usar el mando local, instala también:

```powershell
python -m pip install numpy pynput
```

## Configuración de MongoDB

Crea un archivo `.env` en esta carpeta con la URI de conexión de MongoDB Atlas:

```dotenv
MONGODB_URI=mongodb+srv://<usuario>:<contraseña>@<cluster>/
```

Reemplaza los valores entre `< >` por los de tu clúster. Asegúrate de que la dirección IP del equipo tenga acceso a la base de datos en la configuración de red de Atlas. No compartas ni subas el archivo `.env`; contiene credenciales.

La aplicación usa la base de datos `trayectoria_numerica` y estas colecciones:

- `acelerometro`: mediciones de aceleración.
- `giroscopio`: mediciones de velocidad angular.

## Iniciar la API

Con el entorno virtual activado y `.env` configurado, ejecuta:

```powershell
python -m uvicorn main1:app --host 0.0.0.0 --port 8000
```

La API quedará disponible en el puerto `8000`. La documentación interactiva de FastAPI está en <http://localhost:8000/docs>.

### Endpoints

| Método | Ruta | Datos esperados |
|---|---|---|
| `POST` | `/acelerometro` | `timestamp`, `ax`, `ay`, `az` |
| `POST` | `/giroscopio` | `timestamp`, `gx`, `gy`, `gz` |

Cada campo de medición debe ser una lista; `timestamp` contiene los tiempos y los demás campos sus muestras correspondientes. Por ejemplo:

```json
{
  "timestamp": [0.0, 0.02, 0.04],
  "ax": [0.1, 0.2, 0.15],
  "ay": [0.0, 0.1, 0.05],
  "az": [9.8, 9.7, 9.8]
}
```

Para el giroscopio, envía `gx`, `gy` y `gz` en lugar de `ax`, `ay` y `az`. Las muestras se guardan en MongoDB junto con la fecha de recepción. Una respuesta exitosa tiene la forma:

```json
{
  "estado": "recibido",
  "muestras": 3
}
```

Configura Phyphox para enviar sus mediciones mediante solicitudes HTTP `POST` a la ruta correspondiente del servidor. El celular y el equipo que ejecuta la API deben poder comunicarse por la red; para acceder desde otro dispositivo, usa la dirección IP local del equipo en lugar de `localhost`.

## Ejemplos de Phyphox y Colab

- [`ejemplos/phyphox/Giroscopio_FastAPI-1.phyphox`](ejemplos/phyphox/Giroscopio_FastAPI-1.phyphox): experimento de Phyphox que envía las muestras del giroscopio a `/giroscopio` cada 0.25 segundos. Importa el archivo en Phyphox y cambia `192.168.1.100` en la URL de conexión por la dirección IP local del equipo donde corre la API. El celular debe estar en una red que pueda alcanzar ese equipo.
- [`ejemplos/colab/Mando_Giroscopio_EDO_prueba.ipynb`](ejemplos/colab/Mando_Giroscopio_EDO_prueba.ipynb): cuaderno de Colab para mostrar el modelo, probar datos simulados y visualizar las mediciones y comandos detectados. Sirve como demostración visual: no pulsa teclas. Para la conexión en vivo a MongoDB, configura `MONGODB_URI` en los secretos de Colab.

## Probar la conexión con MongoDB

Con `.env` configurado, ejecuta:

```powershell
python prueba_mongo.py
```

El programa hace un ping a MongoDB Atlas e informa si la conexión funciona.

## Usar el mando local

En otra terminal, con las dependencias instaladas, ejecuta:

```powershell
python mando_local_todo.py
```

El programa lee documentos nuevos de la colección `giroscopio`, calibra el sensor durante aproximadamente dos segundos y traduce la inclinación en pulsaciones de flechas. Mantén el celular quieto durante la calibración y, cuando aparezca el mensaje de listo, selecciona la ventana del juego. Para detenerlo, usa `Ctrl+C`.

El mando inicia desde la medición más reciente y procesa los documentos que lleguen después. La integración angular, los umbrales y el tiempo de calibración se pueden ajustar en las constantes al inicio de `mando_local_todo.py`.

## Archivos principales

- `main1.py`: API FastAPI y almacenamiento de mediciones en MongoDB.
- `mando_local_todo.py`: lectura del giroscopio y control de teclado.
- `prueba_mongo.py`: prueba de conexión a MongoDB Atlas.
