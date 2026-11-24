import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validar_correo(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Debe ser un correo electrónico válido.")
    return value


class BootstrapAdminRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_empresa: int = Field(gt=0, examples=[1])
    correo: str = Field(min_length=5, max_length=254)
    nombre: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128, repr=False)

    @field_validator("correo")
    @classmethod
    def correo_valido(cls, value: str) -> str:
        return _validar_correo(value)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correo: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128, repr=False)

    @field_validator("correo")
    @classmethod
    def correo_valido(cls, value: str) -> str:
        return _validar_correo(value)


class CompradorRegistroRequest(BaseModel):
    """Alta de cuenta de comprador y carrito virtual en una sola operación."""
    model_config = ConfigDict(extra="forbid")
    correo: str = Field(min_length=5, max_length=254)
    nombre: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128, repr=False)
    id_modelo: int = Field(gt=0, examples=[1])

    @field_validator("correo")
    @classmethod
    def correo_valido(cls, value: str) -> str:
        return _validar_correo(value)


class CompradorRegistroResponse(BaseModel):
    id_usuario: int
    id_cliente: int
    id_vehiculo: int
    correo: str
    nombre: str
    tipo_vehiculo: str = "SIMULADO"
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PrincipalResponse(BaseModel):
    id_usuario: int
    id_empresa: int
    correo: str
    nombre: str
    roles: list[str]
