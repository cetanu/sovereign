from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sovereign import json_response_class, logs, server_cipher_container
from sovereign.schemas import EncryptionConfig
from sovereign.utils.crypto.crypto import CipherContainer
from sovereign.utils.crypto.suites import EncryptionType

router = APIRouter()


class EncryptionRequest(BaseModel):
    data: str = Field(..., title="Text to be encrypted", min_length=1, max_length=65535)
    key: Optional[str] = Field(
        None,
        title="Optional encryption key to use to encrypt",
        min_length=44,
        max_length=44,
    )
    encryption_type: str = Field(default="fernet", title="Encryption type to be used")


class DecryptionRequest(BaseModel):
    data: str = Field(..., title="Text to be decrypted", min_length=1, max_length=65535)
    key: str = Field(
        ...,
        title="Encryption key to use to decrypt",
        min_length=44,
        max_length=44,
    )
    encryption_type: str = Field(default="fernet", title="Encryption type to be used")


class DecryptableRequest(BaseModel):
    data: str = Field(..., title="Text to be decrypted", min_length=1, max_length=65535)


@router.post(
    "/decrypt",
    summary="Decrypt provided encrypted data using a provided key",
    response_class=json_response_class,
)
async def _decrypt(request: DecryptionRequest = Body(None)) -> dict[str, Any]:
    user_cipher_container = CipherContainer.from_encryption_configs(
        encryption_configs=[
            EncryptionConfig(
                encryption_key=request.key,
                encryption_type=EncryptionType(request.encryption_type),
            )
        ],
        logger=logs.application_logger.logger,
    )
    return {**user_cipher_container.decrypt_with_type(request.data)}


@router.post(
    "/encrypt",
    summary="Encrypt provided data using this servers key or provided key",
    response_class=json_response_class,
)
async def _encrypt(request: EncryptionRequest = Body(None)) -> dict[str, Any]:
    if request.key:
        user_cipher_container = CipherContainer.from_encryption_configs(
            encryption_configs=[
                EncryptionConfig(
                    encryption_key=request.key,
                    encryption_type=EncryptionType(request.encryption_type),
                )
            ],
            logger=logs.application_logger.logger,
        )
        return {**user_cipher_container.encrypt(request.data)}
    return {**server_cipher_container.encrypt(request.data)}


@router.post(
    "/decryptable",
    summary="Check whether data is decryptable by this server",
    response_class=json_response_class,
)
async def _decryptable(request: DecryptableRequest = Body(None)) -> JSONResponse:
    server_cipher_container.decrypt(request.data)
    return json_response_class({})


@router.get(
    "/generate_key",
    summary="Generate a new asymmetric encryption key",
    response_class=json_response_class,
)
def _generate_key(encryption_type: str = "fernet") -> Dict[str, str]:
    cipher_suite = CipherContainer.get_cipher_suite(EncryptionType(encryption_type))
    return {
        "key": cipher_suite.generate_key().decode(),
        "encryption_type": encryption_type,
    }
