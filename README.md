# 🚗 API Vehículo IoT

Este proyecto es una API hecha con **FastAPI** y **Python**, usando **Programación Orientada a Objetos**.

La API se conecta a una base de datos **MySQL en Amazon RDS** y administra vehículos, comandos y DEMOs mediante procedimientos almacenados. También usa **WebSocket** para enviar eventos al vehículo conectado.

Con esta API puedo:

- Consultar vehículos, comandos, estado e historial.
- Ejecutar un movimiento individual.
- Crear y ejecutar una DEMO con varios movimientos.
- Ver los eventos en tiempo real por WebSocket.

La versión publicada se consulta con HTTPS/WSS. Para desarrollar localmente, se puede iniciar en `localhost:8000`.

---

## Servidor publicado

- **Swagger UI:** https://iotalis.duckdns.org/docs
- **API HTTPS:** https://iotalis.duckdns.org
- **WebSocket seguro del vehículo 5:** `wss://iotalis.duckdns.org/ws/vehiculo/5`

En Swagger puedo ver los endpoints, sus parámetros y los cuerpos JSON.
---

## Cómo correr el proyecto en mi computadora

1. Crear y activar el entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar las dependencias:

```powershell
python -m pip install -r requirements.txt
```

3. Configurar las variables de acceso a MySQL en el entorno local:

```text
DB_HOST=host_de_mi_rds
DB_PORT=3306
DB_NAME=vehiculo_iot
DB_USER=mi_usuario
DB_PASSWORD=mi_contraseña
```

También se pueden establecer en la sesión actual de PowerShell:

```powershell
$env:DB_HOST = "<host-de-mi-rds>"
$env:DB_PORT = "3306"
$env:DB_NAME = "vehiculo_iot"
$env:DB_USER = "<usuario>"
$env:DB_PASSWORD = "<contraseña>"
```

> Si guardo estos datos en un archivo `.env`, ese archivo se queda local y no se sube a GitHub.

4. Iniciar la API:

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

5. Abrir la documentación local:

- Swagger: `http://127.0.0.1:8000/docs`
- WebSocket local: `ws://127.0.0.1:8000/ws/vehiculo/5`

Para conectar con Amazon RDS, la instancia y su red deben permitir que el servidor donde se ejecuta la API acceda a MySQL por el puerto configurado. No se deben abrir accesos públicos a la base sin necesidad.

---

## Qué números uso en las URLs

En los ejemplos de prueba documentados para la base `vehiculo_iot` se usan estos identificadores. Si los datos cambian, primero los consulto en Swagger.

| Qué es | Número de ejemplo | Dónde lo pongo |
|---|---:|---|
| Vehículo | **5** | En la URL: `/vehiculos/5/...` |
| DEMOs que aparecen en los datos compartidos | **2, 4 y 7** | En la URL o en el JSON como `"demo_id"` |
| Comandos del vehículo 5 | **14 al 22 y 35 al 37** | En el JSON como `"comando_id"` |

Comandos de ejemplo:

| `comando_id` | Vehículo | Nombre | `codigo` | Descripción |
|---:|---:|---|---:|---|
| 14 | 5 | AVANZAR | 1 | Mover el vehículo hacia adelante |
| 15 | 5 | RETROCEDER | 2 | Mover el vehículo hacia atrás |
| 16 | 5 | GIRAR_IZQUIERDA | 3 | Girar el vehículo hacia la izquierda |
| 17 | 5 | GIRAR_DERECHA | 4 | Girar el vehículo hacia la derecha |
| 18 | 5 | SUBIR_PALA | 5 | Subir la pala |
| 19 | 5 | BAJAR_PALA | 6 | Bajar la pala |
| 20 | 5 | PALA_IZQUIERDA | 7 | Mover la pala hacia la izquierda |
| 21 | 5 | PALA_DERECHA | 8 | Mover la pala hacia la derecha |
| 22 | 5 | DETENER | 9 | Detener todos los movimientos |
| 35 | 5 | ACTIVAR_SONIDO | 10 | Activar sonido |
| 36 | 5 | ACTIVAR_MODO | 11 | Activar modo |
| 37 | 5 | ENCENDER_LED | 12 | Encender LED |

> Para ejecutar un movimiento envío el `comando_id`, no el `codigo`. El ID identifica el registro del comando y `codigo` es el valor definido para el dispositivo.
>
> La lista anterior incluye únicamente comandos del vehículo 5. Los comandos 26 y 32 de la tabla general pertenecen al vehículo 6 y no se usan en estos ejemplos.

### Pasos de las DEMOs que compartí

En las filas siguientes interpreto las columnas como **`id_demo_movimiento`, `demo_id`, `comando_id`, orden y duración en milisegundos**. La DEMO 2 tiene siete pasos. Los comandos mostrados pertenecen al vehículo 5:

| ID del paso | `demo_id` | `comando_id` | Comando | Orden | Duración (ms) |
|---:|---:|---:|---|---:|---:|
| 14 | 2 | 14 | AVANZAR | 1 | 2000 |
| 15 | 2 | 16 | GIRAR_IZQUIERDA | 2 | 1000 |
| 16 | 2 | 18 | SUBIR_PALA | 3 | 1500 |
| 17 | 2 | 20 | PALA_IZQUIERDA | 4 | 900 |
| 18 | 2 | 21 | PALA_DERECHA | 5 | 900 |
| 19 | 2 | 19 | BAJAR_PALA | 6 | 1500 |
| 20 | 2 | 15 | RETROCEDER | 7 | 2000 |
| 27 | 4 | 14 | AVANZAR | 6 | 2000 |
| 29 | 7 | 15 | RETROCEDER | 1 | 500 |
| 31 | 7 | 20 | PALA_IZQUIERDA | 2 | 500 |
| 32 | 7 | 19 | BAJAR_PALA | 3 | 500 |

Los datos que compartí no muestran `pausa_ms`. En el modelo de la API, si ese campo no viene en el resultado, se usa una pausa predeterminada de **500 ms**. El ID del paso es el que se usa en las rutas para actualizarlo o eliminarlo.

---

## Pruebas con GET

Los GET consultan información y no llevan JSON. La dirección base publicada es `https://iotalis.duckdns.org`.

| URL | Qué número lleva | Qué muestra |
|---|---|---|
| `/` | Ninguno | Mensaje de estado del servicio y rutas útiles |
| `/vehiculos/` | Ninguno | Todos los vehículos |
| `/vehiculos/5` | **5** = ID del vehículo | Datos del vehículo 5 |
| `/vehiculos/5/estado` | **5** = ID del vehículo | El estado más reciente |
| `/vehiculos/5/historial` | **5** = ID del vehículo | Hasta sus 10 movimientos recientes |
| `/vehiculos/5/detalle-completo` | **5** = ID del vehículo | Vehículo, estado, comandos y DEMOs |
| `/comandos/vehiculo/5` | **5** = ID del vehículo | Sus comandos |
| `/comandos/vehiculo/5/detalle` | **5** = ID del vehículo | Sus comandos y máscaras de salida |
| `/demos/vehiculo/5` | **5** = ID del vehículo | Sus DEMOs |
| `/demos/2/movimientos` | **2** = ID de la DEMO | Los pasos de la DEMO 2 |

Ejemplo completo:

```http
GET https://iotalis.duckdns.org/vehiculos/5/historial
```

---

## Pruebas con POST

En Swagger elijo el endpoint, ingreso los valores requeridos y presiono **Execute**. En Postman o Thunder Client elijo **POST**, pongo la URL y escribo el contenido en **Body → raw → JSON**.

### 1. Mover el vehículo (movimiento individual)

Este movimiento **sí se registra en el historial**. El vehículo va en la URL y el comando en el JSON:

```http
POST https://iotalis.duckdns.org/vehiculos/5/movimiento
Content-Type: application/json

{
  "comando_id": 14,
  "origen": "WEB_API"
}
```

- **5** = ID del vehículo, en la URL.
- **14** = ID del comando AVANZAR, en el JSON.
- `origen` indica desde dónde se solicitó el movimiento.

La API comprueba que el vehículo y el comando estén activos, que el comando pertenezca a ese vehículo y que tenga una máscara válida. Después actualiza el estado y registra el movimiento en la misma transacción; luego envía el evento por WebSocket.

> Antes de probar el movimiento, confirma que el vehículo esté conectado y que el área sea segura.

### 2. Iniciar la DEMO

La DEMO ejecuta los pasos configurados en orden y **no agrega esos pasos al historial individual**:

```http
POST https://iotalis.duckdns.org/vehiculos/5/demo/iniciar
Content-Type: application/json

{
  "demo_id": 2
}
```

- **5** = ID del vehículo, en la URL.
- **2** = ID de la DEMO, en el JSON.

La respuesta indica que inició; la secuencia continúa en segundo plano y sus eventos llegan por WebSocket.

### 3. Detener la DEMO

No lleva JSON. Solo funciona si hay una DEMO activa para ese vehículo:

```http
POST https://iotalis.duckdns.org/vehiculos/5/demo/detener
```

### 4. Enviar un mensaje de prueba al dispositivo

Este endpoint envía texto por WebSocket. No mueve el vehículo ni modifica la base de datos:

```http
POST https://iotalis.duckdns.org/vehiculos/5/mensaje
Content-Type: application/json

{
  "texto": "Hola desde la API"
}
```

El mensaje solo llega al vehículo si hay un cliente conectado al WebSocket del vehículo 5.

---

## Cómo ver los eventos del WebSocket

El canal del vehículo 5 es:

```text
wss://iotalis.duckdns.org/ws/vehiculo/5
```

En Postman creo una solicitud nueva de tipo **WebSocket**, pego la dirección y presiono **Connect**. Al conectar, el servidor debe enviar `conexion_establecida`. También puedo enviar un texto desde Postman; la API responde con `eco_cliente_ws`.

Otra opción es usar la consola del navegador:

```javascript
const ws = new WebSocket("wss://iotalis.duckdns.org/ws/vehiculo/5");
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.onopen = () => console.log("WebSocket conectado");
ws.onerror = (e) => console.error("Error en WebSocket", e);
```

Dejo abierta la conexión y luego inicio una DEMO o envío un movimiento desde Swagger. Según la operación, puedo ver:

| Evento | Cuándo sale |
|---|---|
| `conexion_establecida` | Cuando el servidor acepta la conexión |
| `eco_cliente_ws` | Cuando envío texto desde el cliente WebSocket |
| `movimiento_individual` | Cuando se procesa un movimiento individual |
| `consulta` | Cuando se consultan comandos o DEMOs |
| `mensaje` | Cuando se envía un texto de prueba por la API |
| `demo_inicio` | Cuando comienza la DEMO |
| `demo_movimiento` | En cada paso de la DEMO |
| `demo_fin` | Cuando termina la secuencia |
| `demo_cancelada` | Cuando se detiene la DEMO |
| `demo_error` | Si ocurre un error durante la DEMO |

Ejemplo simplificado de un paso:

```json
{
  "tipo": "demo_movimiento",
  "vehiculo_id": 5,
  "comando_id": 14,
  "codigo": 1,
  "demo_id": 2,
  "orden": 1,
  "duracion_ms": 2000,
  "pausa_ms": 500,
  "nombre": "AVANZAR",
  "mascara": 1,
  "marca_temporal": "2026-11-04T10:30:00"
}
```

La forma exacta del evento depende del tipo de mensaje. Algunos campos generales, como `comando_id` o `codigo`, pueden ser `null` cuando no aplican.

---

## ¿Qué se guarda en el historial?

| Acción | ¿Actualiza el estado? | ¿Se guarda en el historial individual? |
|---|:---:|:---:|
| Movimiento individual | Sí | **Sí** |
| DEMO | Sí, en cada paso | **No** |

El movimiento individual llama a `sp_actualizar_estado` y `sp_registrar_historial` dentro de una transacción. En la DEMO, cada paso actualiza el estado y se transmite por WebSocket, pero no se registra como movimiento individual.

El endpoint de historial devuelve los **10 registros más recientes** según el procedimiento almacenado y el límite aplicado por el repositorio de la API.

---

## Crear, cambiar y borrar con POST

Todos los cambios se hacen con POST, de acuerdo con las rutas actuales de esta API. En los siguientes ejemplos uso IDs de muestra; antes de modificar o borrar en el servidor publicado, verifico que sean los IDs correctos. No borro el vehículo 5 si es el que está conectado al dispositivo.

### Vehículos

| URL | Qué ID lleva | JSON |
|---|---|---|
| `POST /vehiculos/` | Ninguno | Sí, datos del vehículo |
| `POST /vehiculos/5/actualizar` | **5** = ID del vehículo | Sí, datos actualizados |
| `POST /vehiculos/5/eliminar` | **5** = ID del vehículo | No |

Crear vehículo:

```json
{
  "nombre": "Excavadora 02",
  "descripcion": "Vehículo de prueba"
}
```

Actualizar vehículo:

```json
{
  "nombre": "Excavadora 01",
  "descripcion": "Excavadora controlada por ESP",
  "activo": true
}
```

### Comandos

| URL | Qué ID lleva |
|---|---|
| `POST /comandos/` | El ID del vehículo va en el JSON |
| `POST /comandos/14/actualizar` | **14** = ID del comando |
| `POST /comandos/14/eliminar` | **14** = ID del comando; no lleva JSON |
| `POST /comandos/14/mascara` | **14** = ID del comando |

Crear comando:

```json
{
  "vehiculo_id": 5,
  "nombre": "GIRAR_360",
  "codigo": 10,
  "descripcion": "Gira sobre su propio eje",
  "mascara": 64
}
```

El campo `mascara` es opcional; si no se envía, la API intenta asignarla según el nombre del comando. Para actualizar, también se puede enviar una máscara:

```json
{
  "nombre": "AVANZAR",
  "codigo": 1,
  "descripcion": "Mueve el vehículo hacia adelante",
  "activo": true,
  "mascara": 1
}
```

Asignar una máscara:

```json
{
  "mascara": 1
}
```

### DEMOs

| URL | Qué ID lleva |
|---|---|
| `POST /demos/` | El ID del vehículo va en el JSON |
| `POST /demos/2/actualizar` | **2** = ID de la DEMO |
| `POST /demos/2/eliminar` | **2** = ID de la DEMO; no lleva JSON |

Crear DEMO:

```json
{
  "vehiculo_id": 5,
  "nombre": "Demo corta",
  "descripcion": "Prueba con pocos movimientos"
}
```

Actualizar DEMO:

```json
{
  "nombre": "Demo principal",
  "descripcion": "Secuencia principal",
  "activo": true
}
```

### Movimientos de una DEMO

| URL | Qué ID lleva |
|---|---|
| `POST /demos/2/movimientos` | **2** = ID de la DEMO |
| `POST /demos/movimientos/14/actualizar` | **14** = ID del primer paso de la DEMO 2 |
| `POST /demos/movimientos/14/eliminar` | **14** = ID del primer paso; no lleva JSON |

El ID del paso lo consulto primero con `GET /demos/2/movimientos`; en los datos compartidos, el primer paso tiene `id_demo_movimiento` 14.

La DEMO 2 ya tiene pasos con orden del 1 al 7. Para agregar uno nuevo al final, el ejemplo usa el orden 8 (solo lo envío si quiero modificar la DEMO):

```json
{
  "comando_id": 22,
  "orden": 8,
  "duracion_ms": 1000,
  "pausa_ms": 500
}
```

Actualizar un paso:

```json
{
  "comando_id": 15,
  "orden": 1,
  "duracion_ms": 2000,
  "pausa_ms": 500
}
```

> `duracion_ms` y `pausa_ms` son milisegundos; `1000` equivale a un segundo.

---

## Los 21 Stored Procedures de la guía técnica

La API usa procedimientos almacenados parametrizados para comunicarse con MySQL. Esta es la lista de **21 operaciones principales** de la guía técnica y dónde se ejecutan:

| # | Stored Procedure | Dónde se usa |
|---:|---|---|
| 1 | `sp_obtener_vehiculos` | GET `/vehiculos/` |
| 2 | `sp_obtener_vehiculo` | GET `/vehiculos/{vehiculo_id}` |
| 3 | `sp_crear_vehiculo` | POST `/vehiculos/` |
| 4 | `sp_actualizar_vehiculo` | POST `/vehiculos/{vehiculo_id}/actualizar` |
| 5 | `sp_eliminar_vehiculo` | POST `/vehiculos/{vehiculo_id}/eliminar` |
| 6 | `sp_obtener_comandos_vehiculo` | GET `/comandos/vehiculo/{vehiculo_id}` |
| 7 | `sp_crear_comando` | POST `/comandos/` |
| 8 | `sp_actualizar_comando` | POST `/comandos/{comando_id}/actualizar` |
| 9 | `sp_eliminar_comando` | POST `/comandos/{comando_id}/eliminar` |
| 10 | `sp_obtener_demos` | GET `/demos/vehiculo/{vehiculo_id}` |
| 11 | `sp_obtener_movimientos_demo` | GET `/demos/{demo_id}/movimientos` y al iniciar la DEMO |
| 12 | `sp_crear_demo` | POST `/demos/` |
| 13 | `sp_actualizar_demo` | POST `/demos/{demo_id}/actualizar` |
| 14 | `sp_eliminar_demo` | POST `/demos/{demo_id}/eliminar` |
| 15 | `sp_agregar_movimiento_demo` | POST `/demos/{demo_id}/movimientos` |
| 16 | `sp_actualizar_movimiento_demo` | POST `/demos/movimientos/{movimiento_id}/actualizar` |
| 17 | `sp_eliminar_movimiento_demo` | POST `/demos/movimientos/{movimiento_id}/eliminar` |
| 18 | `sp_obtener_estado` | GET `/vehiculos/{vehiculo_id}/estado` |
| 19 | `sp_actualizar_estado` | Movimiento individual y cada paso de una DEMO |
| 20 | `sp_registrar_historial` | Movimiento individual, junto con la actualización del estado |
| 21 | `sp_obtener_historial` | GET `/vehiculos/{vehiculo_id}/historial` |

Por grupos, la guía cuenta 5 operaciones de vehículos, 4 de comandos, 8 de DEMOs y pasos y 4 de estado e historial.

### Dos procedimientos adicionales de la implementación actual

El código de este repositorio también usa estos procedimientos para completar las operaciones:

- `sp_obtener_comandos_detalle` — GET `/comandos/vehiculo/{vehiculo_id}/detalle`, incluye las máscaras de salida.
- `sp_actualizar_mascara_comando` — POST `/comandos/{comando_id}/mascara`, persiste la máscara del comando.

Por eso, la implementación actual llama **23 nombres únicos** de procedimientos almacenados. La API no los crea: deben estar instalados en la base MySQL de Amazon RDS.

---

## Códigos que me puede responder

| Código | Qué quiere decir |
|---:|---|
| `200` | La solicitud se procesó correctamente, por ejemplo, al iniciar una DEMO. |
| `201` | Se creó un recurso o se registró un movimiento individual. |
| `400` | Los datos no son válidos, el comando no se puede ejecutar o la DEMO no puede iniciarse. |
| `404` | No se encontró un vehículo o estado solicitado; algunas rutas específicas también devuelven 404 si no existe el comando. |
| `409` | Ya hay una DEMO activa, hay un conflicto de integridad o se intenta eliminar un vehículo con una DEMO en ejecución. |
| `422` | El JSON está incompleto o no cumple el formato que valida Pydantic. |
| `500` | Ocurrió un error interno del servidor o de la base de datos. |

---

## Si algo falla

| Problema | Qué reviso |
|---|---|
| La API no conecta con RDS | Verifico `DB_HOST`, puerto, usuario, base, contraseña y las reglas de red de RDS |
| Postman no conecta al WebSocket | Creo una solicitud **WebSocket**, uso `wss://` en producción y reviso que el vehículo exista |
| Postman conecta pero no veo más eventos | Reviso **Messages**, mantengo la conexión abierta y luego mando texto o ejecuto una acción para el mismo vehículo |
| Sale `409` al iniciar la DEMO | Ya existe una DEMO activa para ese vehículo; espero a que termine o la detengo |
| Sale `400` al ejecutar un movimiento | Reviso que el comando pertenezca al vehículo, esté activo y tenga una máscara configurada |
| Sale `422` | Comparo los nombres y tipos del JSON con el esquema que muestra Swagger |
| Sale error de módulo en local | Activo `.venv` y ejecuto `python -m pip install -r requirements.txt` |

---

## Carpetas del proyecto

```text
config/          Conexión y configuración de la base de datos
core/            Contenedor y reglas compartidas, como máscaras
models/          Entidades de vehículos, comandos, DEMOs y estado
repositories/    Consultas y ejecución de Stored Procedures
services/        Reglas para movimientos, DEMOs y eliminaciones
routers/          Endpoints GET, POST y WebSocket
schemas/          Validación de los JSON con Pydantic
ws_manager/       Eventos y conexiones WebSocket por vehículo
docs/             Manuscrito visual de las 21 operaciones
main.py           Configura y enciende la API
requirements.txt  Dependencias de Python
```

---
