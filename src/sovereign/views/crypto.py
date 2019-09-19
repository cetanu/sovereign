from pydantic import BaseModel, Schema
from fastapi import APIRouter, Body
from starlette.responses import UJSONResponse

from sovereign.middlewares import get_request_id
from sovereign.utils.crypto import encrypt, decrypt, generate_key

router = APIRouter()


class EncryptionRequest(BaseModel):
    data: str = Schema(..., title='Text to be encrypted', min_length=1, max_length=65535)
    key: str = Schema(None, title='Optional Fernet encryption key to use to encrypt', min_length=44, max_length=44)


class DecryptionRequest(BaseModel):
    data: str = Schema(..., title='Text to be decrypted', min_length=1, max_length=65535)
    key: str = Schema(..., title='Fernet encryption key to use to decrypt', min_length=44, max_length=44)


class DecryptableRequest(BaseModel):
    data: str = Schema(..., title='Text to be decrypted', min_length=1, max_length=65535)


@router.post('/decrypt', summary='Decrypt provided encrypted data using a provided key', response_class=UJSONResponse)
async def _decrypt(request: DecryptionRequest = Body(None)):
    return {'result': decrypt(request.data, request.key)}


@router.post('/encrypt', summary='Encrypt provided data using this servers key', response_class=UJSONResponse)
async def _encrypt(request: EncryptionRequest = Body(None)):
    return {'result': encrypt(data=request.data, key=request.key)}


@router.post('/decryptable', summary='Check whether data is decryptable by this server', response_class=UJSONResponse)
async def _decryptable(request: DecryptableRequest = Body(None)):
    try:
        decrypt(request.data)
        ret = {}
        code = 200
    except KeyError as e:
        ret = {
            'error': str(e),
            'request_id': get_request_id()
        }
        code = 500
    return UJSONResponse(ret, status_code=code)


@router.get('/generate_key', summary='Generate a new asymmetric encryption key', response_class=UJSONResponse)
def _generate_key():
    return {'result': generate_key()}
