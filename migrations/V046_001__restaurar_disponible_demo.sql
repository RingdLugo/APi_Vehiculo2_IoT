-- Reparacion de compatibilidad del panel y sesiones de exhibicion.
-- Version: V046_001
-- Caso: V044_001 pudo revertirse o quedar inconsistente; el API requiere
-- inventario_vehiculos.disponible_demo para filtrar unidades de exhibicion.
-- Seguro para re-ejecucion: agrega cada objeto unicamente si hace falta.
-- No actualiza ni elimina filas existentes; la columna nueva inicia en 0.

USE `vehiculo_iot`;

SELECT DATABASE() AS base_activa, VERSION() AS version_mysql;

-- La columna puede faltar aunque la migracion original aparezca aplicada.
SET @existe_columna := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'inventario_vehiculos'
    AND COLUMN_NAME = 'disponible_demo'
);
SET @ddl := IF(
  @existe_columna = 0,
  'ALTER TABLE `inventario_vehiculos` ADD COLUMN `disponible_demo` TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''Unidad autorizada para exhibicion publica''',
  'SELECT ''La columna disponible_demo ya existe'' AS resultado'
);
PREPARE migracion_stmt FROM @ddl;
EXECUTE migracion_stmt;
DEALLOCATE PREPARE migracion_stmt;

SET @existe_indice := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'inventario_vehiculos'
    AND INDEX_NAME = 'ix_inventario_demo_estado'
);
SET @ddl := IF(
  @existe_indice = 0,
  'ALTER TABLE `inventario_vehiculos` ADD KEY `ix_inventario_demo_estado` (`disponible_demo`, `estado`, `id_vehiculo`)',
  'SELECT ''El indice ix_inventario_demo_estado ya existe'' AS resultado'
);
PREPARE migracion_stmt FROM @ddl;
EXECUTE migracion_stmt;
DEALLOCATE PREPARE migracion_stmt;

SET @existe_check := (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND TABLE_NAME = 'inventario_vehiculos'
    AND CONSTRAINT_NAME = 'chk_inventario_disponible_demo'
    AND CONSTRAINT_TYPE = 'CHECK'
);
SET @ddl := IF(
  @existe_check = 0,
  'ALTER TABLE `inventario_vehiculos` ADD CONSTRAINT `chk_inventario_disponible_demo` CHECK (`disponible_demo` IN (0,1))',
  'SELECT ''La restriccion chk_inventario_disponible_demo ya existe'' AS resultado'
);
PREPARE migracion_stmt FROM @ddl;
EXECUTE migracion_stmt;
DEALLOCATE PREPARE migracion_stmt;

INSERT IGNORE INTO `migraciones_esquema` (`version`, `archivo`, `observaciones`)
VALUES ('V046_001', 'V046_001__restaurar_disponible_demo.sql',
        'Restaura columna, indice y check requeridos por el API; no modifica filas existentes.');

-- Verificacion posterior: deben aparecer columna, indice y CHECK.
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'inventario_vehiculos'
  AND COLUMN_NAME = 'disponible_demo';

SELECT INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'inventario_vehiculos'
  AND INDEX_NAME = 'ix_inventario_demo_estado'
ORDER BY SEQ_IN_INDEX;

SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE
FROM information_schema.TABLE_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = DATABASE()
  AND TABLE_NAME = 'inventario_vehiculos'
  AND CONSTRAINT_NAME = 'chk_inventario_disponible_demo';
