-- Fase 7/10 — identificar unidades públicas de exhibición sin publicar inventario privado.
-- Versión: V044_001
-- Requiere MySQL 8.0+ / InnoDB. NO ejecutar en RDS productivo sin respaldo y prueba aislada.
-- Esta migración no modifica IDs, relaciones, unidades vendidas ni historial.

USE vehiculo_iot;

SELECT DATABASE() AS base_activa,
       VERSION() AS version_mysql,
       COUNT(*) AS filas_inventario
FROM inventario_vehiculos;

SELECT COLUMN_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'inventario_vehiculos'
  AND COLUMN_NAME = 'disponible_demo';

-- Si la consulta anterior devuelve una fila, la columna ya existe y no se ejecuta el ALTER.
ALTER TABLE inventario_vehiculos
  ADD COLUMN disponible_demo TINYINT(1) NOT NULL DEFAULT 0
    COMMENT 'Unidad autorizada para exhibición pública; no equivale a venta ni a permiso de control',
  ADD KEY ix_inventario_demo_estado (disponible_demo, estado, id_vehiculo),
  ADD CONSTRAINT chk_inventario_disponible_demo CHECK (disponible_demo IN (0,1));

SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'inventario_vehiculos'
  AND COLUMN_NAME = 'disponible_demo';

SELECT COUNT(*) AS unidades_marcadas_para_demo
FROM inventario_vehiculos
WHERE disponible_demo = 1;

