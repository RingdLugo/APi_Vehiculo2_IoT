-- Configuración de movimientos virtuales por comprador y carrito simulado.
-- No contiene IDs de comandos físicos ni altera vehículos o historiales.
USE `vehiculo_iot`;

CREATE TABLE IF NOT EXISTS `configuracion_simulacion` (
  `id_usuario` INT NOT NULL,
  `id_vehiculo` INT NOT NULL,
  `movimientos` JSON NOT NULL,
  `asignaciones` JSON NOT NULL,
  `creado_en` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `actualizado_en` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_usuario`, `id_vehiculo`),
  KEY `ix_configuracion_simulacion_vehiculo` (`id_vehiculo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO `migraciones_esquema` (`version`, `archivo`, `observaciones`)
VALUES ('V048_001', 'V048_001__movimientos_personalizados_simulados.sql',
        'Configuración aislada de movimientos y joystick para carrito SIMULADO; sin impacto físico.');

SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='configuracion_simulacion'
ORDER BY ORDINAL_POSITION;
