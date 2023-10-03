from typing import Dict
from pydantic import BaseModel, Field
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from sovereign import json_response_class, cipher_suite
from sovereign.utils.crypto import generate_key

router = APIRouter()


class EncryptionRequest(BaseModel):
    data: str = Field(..., title="Text to be encrypted", min_length=1, max_length=65535)
    key: str = Field(
        None,
        title="Optional Fernet encryption key to use to encrypt",
        min_length=44,
        max_length=44,
    )


class DecryptionRequest(BaseModel):
    data: str = Field(..., title="Text to be decrypted", min_length=1, max_length=65535)
    key: str = Field(
        ...,
        title="Fernet encryption key to use to decrypt",
        min_length=44,
        max_length=44,
    )


class DecryptableRequest(BaseModel):
    data: str = Field(..., title="Text to be decrypted", min_length=1, max_length=65535)


@router.post(
    "/decrypt",
    summary="Decrypt provided encrypted data using a provided key",
    response_class=json_response_class,
)
async def _decrypt(request: DecryptionRequest = Body(None)) -> Dict[str, str]:
    return {"result": cipher_suite.decrypt(request.data, request.key)}


@router.post(
    "/encrypt",
    summary="Encrypt provided data using this servers key",
    response_class=json_response_class,
)
async def _encrypt(request: EncryptionRequest = Body(None)) -> Dict[str, str]:
    return {"result": cipher_suite.encrypt(data=request.data, key=request.key)}


@router.post(
    "/decryptable",
    summary="Check whether data is decryptable by this server",
    response_class=json_response_class,
)
async def _decryptable(request: DecryptableRequest = Body(None)) -> JSONResponse:
    cipher_suite.decrypt(request.data)
    return json_response_class({})


@router.get(
    "/generate_key",
    summary="Generate a new asymmetric encryption key",
    response_class=json_response_class,
)
def _generate_key() -> Dict[str, str]:
    return {"result": generate_key()}
