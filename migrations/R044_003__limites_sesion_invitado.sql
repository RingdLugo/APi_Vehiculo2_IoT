-- Reversión de V044_003. Revisa primero el uso y conserva un respaldo.
-- DDL en MySQL realiza commit implícito.
USE vehiculo_iot;
SELECT COUNT(*) AS sesiones_con_uso FROM sesiones_invitado WHERE comandos_usados>0;
ALTER TABLE sesiones_invitado
  DROP COLUMN ultimo_comando_en,
  DROP COLUMN comandos_usados;
