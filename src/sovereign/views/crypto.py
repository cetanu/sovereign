from pydantic import BaseModel, Schema
from fastapi import APIRouter, Body
from starlette.responses import JSONResponse
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


@router.post('/crypto/decrypt', summary='Decrypt provided encrypted data using a provided key')
async def _decrypt(request: DecryptionRequest = Body(None)):
    try:
        ret = {
            'result': decrypt(request.data, request.key)
        }
        code = 200
    except KeyError:
        ret = {
            'error': 'A key must be supplied to use for decryption'
        }
        code = 400
    return JSONResponse(content=ret, status_code=code)


@router.post('/crypto/encrypt', summary='Encrypt provided data using this servers key')
async def _encrypt(request: EncryptionRequest = Body(None)):
    ret = {
        'result': encrypt(data=request.data, key=request.key)
    }
    return JSONResponse(content=ret)


@router.post('/crypto/decryptable', summary='Check whether data is decryptable by this server')
async def _decryptable(request: DecryptableRequest = Body(None)):
    try:
        decrypt(request.data)
        ret = {}
        code = 200
    except KeyError as e:
        ret = {
            'error': str(e),
            # TODO: add request id
        }
        code = 500
    return JSONResponse(content=ret, status_code=code)


@router.get('/crypto/generate_key', summary='Generate a new asymmetric encryption key')
def _generate_key():
    return JSONResponse(content={'result': generate_key()})
