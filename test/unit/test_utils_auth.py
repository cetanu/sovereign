import pytest
from fastapi.exceptions import HTTPException
from sovereign.utils.crypto import encrypt
from sovereign.utils.auth import authenticate, validate


def test_validate(auth_string):
    assert validate(auth_string)


@pytest.mark.parametrize(
    'bad_input',
    [
        98123197824,
        1.0,
        object,
        dict(),
    ]
)
def test_validate_fails_on_bad_input(bad_input):
    with pytest.raises(HTTPException) as e:
        validate(bad_input)
        assert e.status_code == 400


def test_validate_returns_false_for_bad_password():
    assert not validate(encrypt('not valid'))


def test_authenticate(discovery_request, auth_string):
    discovery_request.node.metadata['auth'] = auth_string
    authenticate(discovery_request)


def test_authenticate_rejects_authless_req(discovery_request):
    with pytest.raises(HTTPException) as e:
        authenticate(discovery_request)
        assert e.status_code == 401


def test_authenticate_rejects_incorrect_auth(discovery_request):
    discovery_request.node.metadata['auth'] = encrypt('not valid')
    with pytest.raises(HTTPException) as e:
        authenticate(discovery_request)
        assert e.status_code == 401


@pytest.mark.parametrize(
    'bad_input',
    [
        98123197824,
        1.0,
        object,
        dict(),
    ]
)
def test_authenticate_rejects_bad_input(bad_input):
    with pytest.raises(HTTPException) as e:
        authenticate(bad_input)
        assert e.status_code == 400
