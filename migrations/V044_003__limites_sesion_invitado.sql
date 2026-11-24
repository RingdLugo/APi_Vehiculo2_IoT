-- Fase 10.3/10.4: control de frecuencia y cantidad para sesiones públicas.
-- Probar sobre una copia y revisar el respaldo antes de ejecutar en RDS.
USE vehiculo_iot;

SELECT COLUMN_NAME FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='sesiones_invitado'
  AND COLUMN_NAME IN ('comandos_usados','ultimo_comando_en');

-- Ejecutar solo si ninguna de las dos columnas existe.
ALTER TABLE sesiones_invitado
  ADD COLUMN comandos_usados INT UNSIGNED NOT NULL DEFAULT 0,
  ADD COLUMN ultimo_comando_en TIMESTAMP(3) NULL DEFAULT NULL;

SELECT COLUMN_NAME,COLUMN_TYPE,COLUMN_DEFAULT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='sesiones_invitado'
  AND COLUMN_NAME IN ('comandos_usados','ultimo_comando_en');
