# Integración del vehículo físico (ID 1 después de V047_001)

## Flujo de control

1. El administrador inicia sesión y, en **Administración → Unidades**, selecciona el carrito físico con **Usar esta unidad**.
2. El navegador usa las rutas autenticadas `/cuenta/vehiculos/1/...`. La API valida el inventario y la empresa antes de operar.
3. Al enviar un comando o iniciar una DEMO, FastAPI registra la operación y publica el evento para el vehículo 1.
4. El ESP8266 se conecta a `wss://iotalis.duckdns.org/ws/vehiculo/1`, se autentica con `IOT_DEVICE_TOKEN_1` y procesa el evento recibido.

Los carritos `SIMULADO` de compradores conservan sus propios IDs. No se les asigna el carrito físico.

## Pasos coordinados con V047_001

- No cargar este firmware ni cambiar el `.env` antes de aplicar `V047_001__renumerar_vehiculo_fisico_y_comandos.sql` y verificar que el inventario físico aparece con ID 1.
- Renombrar la variable ya configurada en el servidor de `IOT_DEVICE_TOKEN_5` a `IOT_DEVICE_TOKEN_1`, conservando el valor secreto; reiniciar el servicio API.
- Cargar el firmware actualizado. En el portal WiFiManager establece host `iotalis.duckdns.org`, ID `1` y el mismo token. Los valores guardados en LittleFS prevalecen sobre los valores predeterminados del firmware.
- La huella SHA-1 TLS debe coincidir con el certificado vigente. La conexión WSS confirma que el ESP está conectado; no confirma eléctricamente el estado de motores o relevadores.
