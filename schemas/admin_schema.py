from typing import Any

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModeloCreate(InputModel):
    codigo: str = Field(min_length=1, max_length=60)
    marca: str = Field(min_length=1, max_length=100)
    nombre: str = Field(min_length=1, max_length=120)
    microcontrolador: str | None = Field(default=None, max_length=50)


class ModeloPatch(InputModel):
    marca: str | None = Field(default=None, min_length=1, max_length=100)
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    microcontrolador: str | None = Field(default=None, max_length=50)
    estado: str | None = Field(default=None, pattern="^(ACTIVO|INACTIVO|BAJA)$")


class UnidadCreate(InputModel):
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)
    microcontrolador: str | None = Field(default=None, max_length=50)
    id_modelo: int = Field(gt=0)


class UnidadPatch(InputModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)
    activo: bool | None = None
    id_modelo: int | None = Field(default=None, gt=0)
    disponible_demo: bool | None = None


class ClienteCreate(InputModel):
    nombre: str = Field(min_length=1, max_length=160)
    correo_contacto: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128, repr=False)
    id_modelo: int = Field(gt=0)
    telefono_contacto: str | None = Field(default=None, max_length=32)

    @field_validator("correo_contacto")
    @classmethod
    def correo_valido(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Debe ser un correo electrónico válido.")
        return value


class ClientePatch(InputModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    correo_contacto: str | None = Field(default=None, max_length=254)
    telefono_contacto: str | None = Field(default=None, max_length=32)
    estado: str | None = Field(default=None, pattern="^(ACTIVO|INACTIVO|BAJA)$")


class UsuarioCreate(InputModel):
    correo: str = Field(min_length=5, max_length=254, examples=["usuario@example.test"])
    nombre: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128, repr=False)
    id_modelo: int = Field(gt=0, description="Modelo comercial del carrito virtual que se creará automáticamente.")

    @field_validator("correo")
    @classmethod
    def correo_valido(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Debe ser un correo electrónico válido.")
        return value


class UsuarioEstadoPatch(InputModel):
    estado: str = Field(pattern="^(ACTIVO|BLOQUEADO|BAJA)$")


class UsuarioRolesPatch(InputModel):
    roles: list[str] = Field(min_length=1, max_length=2)

    @field_validator("roles")
    @classmethod
    def validar_roles(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().upper() for value in values]
        if len(set(normalized)) != len(normalized):
            raise ValueError("No repitas un rol.")
        if not set(normalized).issubset({"ADMINISTRADOR", "USUARIO"}):
            raise ValueError("Solo se asignan roles de cuenta; Invitado usa una sesión temporal.")
        return normalized


class AsignacionCreate(InputModel):
    id_vehiculo: int = Field(gt=0)
    id_cliente: int = Field(gt=0)
    motivo: str | None = Field(default=None, max_length=255)


class AsignacionCerrar(InputModel):
    estado: str = Field(pattern="^(FINALIZADA|REVOCADA)$")
    motivo: str | None = Field(default=None, max_length=255)


class SesionInvitadoCreate(InputModel):
    id_vehiculo: int = Field(gt=0)
    id_demo: int | None = Field(default=None, gt=0)
    duracion_minutos: int = Field(gt=0, le=120)
    comandos_permitidos: list[int] = Field(min_length=1, max_length=32)


class SolicitudDemoPublica(InputModel):
    id_modelo: int = Field(gt=0, examples=[1])
    id_demo: int | None = Field(default=None, gt=0)


class MovimientoInvitado(InputModel):
    """Comando solicitado con la credencial temporal de invitado."""
    comando_id: int = Field(gt=0, examples=[14])
    estado_salida: bool | None = Field(
        default=None,
        description="Estado deseado para LED/sonido cuando ese comando sea conmutable.",
        examples=[True],
    )


class AdminDemoCreate(InputModel):
    id_vehiculo: int = Field(gt=0, examples=[5])
    nombre: str = Field(min_length=1, max_length=80, examples=["Demo de bienvenida"])
    descripcion: str | None = Field(default=None, max_length=255)


class AdminDemoPatch(InputModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)
    activo: bool | None = None


class AdminPasoCreate(InputModel):
    id_comando: int = Field(gt=0, examples=[14])
    orden: int = Field(ge=1, examples=[1])
    duracion_ms: int = Field(ge=0, le=3_600_000, examples=[1000])
    pausa_ms: int = Field(ge=0, le=3_600_000, examples=[500])


class AdminPasoPatch(InputModel):
    id_comando: int | None = Field(default=None, gt=0)
    orden: int | None = Field(default=None, ge=1)
    duracion_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    pausa_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class AuditResponse(BaseModel):
    id_auditoria: int
    id_empresa: int | None
    id_usuario: int | None
    accion: str
    entidad: str
    id_entidad: str | None
    resultado: str
    ocurrido_en: Any


class AdminDashboardResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "modelos_activos": 3, "unidades_totales": 8,
        "unidades_vendidas_asignadas": 4, "unidades_disponibles_prueba": 3,
        "clientes_activos": 4, "demos_activas": 2,
        "unidades_con_sesion_wss": 1,
        "unidades_con_dispositivo_wss": 1,
        "nota_wss": "Cuenta sesiones WSS autenticadas del navegador.",
        "nota_dispositivo_wss": "Cuenta ESP8266 autenticados conectados a este proceso API; no confirma el estado eléctrico de las salidas.",
        "generado_en": "2026-11-22T18:30:00Z"
    }]})
    modelos_activos: int
    unidades_totales: int
    unidades_vendidas_asignadas: int
    unidades_disponibles_prueba: int
    clientes_activos: int
    demos_activas: int
    unidades_con_sesion_wss: int
    unidades_con_dispositivo_wss: int
    nota_wss: str
    nota_dispositivo_wss: str
    generado_en: Any
