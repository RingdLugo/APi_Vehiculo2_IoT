import logging
import os

import pymysql

import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from schemas.auth_schema import (BootstrapAdminRequest, CompradorRegistroRequest,
                                 CompradorRegistroResponse, LoginRequest,
                                 PrincipalResponse, TokenResponse)
from security.dependencies import current_principal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/bootstrap-admin", status_code=status.HTTP_201_CREATED,
             summary="Crear el primer administrador de una empresa",
             description=("Uso único protegido por BOOTSTRAP_ADMIN_KEY. Requiere que la empresa "
                          "exista y no tenga administrador activo."),
             responses={401: {"description": "Clave bootstrap inválida."},
                        404: {"description": "Bootstrap deshabilitado."},
                        409: {"description": "Ya existe administrador o correo duplicado."}})
def bootstrap_admin(
    data: BootstrapAdminRequest,
    request: Request,
    x_bootstrap_key: str | None = Header(default=None, alias="X-Bootstrap-Key"),
):
    service = request.app.state.auth_service
    try:
        user_id = service.bootstrap_admin(
            data.id_empresa, data.correo, data.nombre, data.password, x_bootstrap_key
        )
        return {"id_usuario": user_id, "mensaje": "Administrador creado."}
    except PermissionError as exc:
        code = 404 if "deshabilitado" in str(exc) else 401
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/token", response_model=TokenResponse, summary="Iniciar sesión",
             responses={401: {"description": "Correo o contraseña incorrectos."},
                        429: {"description": "Límite temporal de intentos alcanzado."}})
def login(data: LoginRequest, request: Request):
    try:
        result = request.app.state.auth_service.iniciar_sesion(data.correo, data.password)
    except RuntimeError as exc:
        logger.error("Configuración de autenticación incompleta: %s", exc)
        raise HTTPException(status_code=503, detail="Autenticación no configurada.") from exc
    if not result:
        raise HTTPException(
            status_code=401, detail="Correo o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result


@router.get("/modelos", summary="Consultar modelos disponibles para compra")
def modelos_disponibles(request: Request):
    return request.app.state.auth_repository.modelos_disponibles_compra()


@router.post("/registro-comprador", response_model=CompradorRegistroResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Registrar comprador y crear automáticamente su carrito simulado",
             description=("Crea cuenta, cliente y carrito virtual enlazado al modelo seleccionado. "
                          "No reserva ni representa una unidad ESP física."),
             responses={404: {"description": "Empresa, modelo o plantilla de comandos no disponible."},
                        409: {"description": "El correo ya está registrado."},
                        429: {"description": "Límite temporal de registros alcanzado."}})
def registrar_comprador(data: CompradorRegistroRequest, request: Request):
    try:
        company_id = int(os.getenv("DEFAULT_COMPANY_ID", "1"))
        return request.app.state.auth_service.registrar_comprador(
            company_id, data.correo, data.nombre, data.password, data.id_modelo
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (FileExistsError, pymysql.err.IntegrityError) as exc:
        raise HTTPException(status_code=409, detail="El correo o la cuenta ya está registrado.") from exc
    except RuntimeError as exc:
        logger.error("No se pudo registrar comprador: %s", exc)
        raise HTTPException(status_code=503, detail="No se pudo completar el registro.") from exc


@router.get("/me", response_model=PrincipalResponse, summary="Consultar usuario autenticado")
def me(principal: dict = Depends(current_principal)):
    return principal


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT,
             summary="Cerrar sesión e invalidar el token Bearer actual",
             responses={401: {"description": "Token ausente, inválido o previamente revocado."}})
async def logout(request: Request, principal: dict = Depends(current_principal),
                 authorization: str | None = Header(default=None, alias="Authorization")):
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Se requiere un token Bearer.")
    try:
        await asyncio.to_thread(request.app.state.auth_service.revocar_token, token, principal["id_usuario"])
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    await request.app.state.connection_manager.cerrar_usuario(principal["id_usuario"])
    return Response(status_code=204)
