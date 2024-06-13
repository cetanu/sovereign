import json

import pytest
from botocore.exceptions import ClientError
from starlette.exceptions import HTTPException
from starlette.testclient import TestClient

from sovereign.app import generic_error_response

_S3_ERROR_MSG = "An error occurred (AccessDenied) when calling the ListObjects operation: Access Denied"
_S3_RESPONSE = {
    "Error": {"Code": "AccessDenied", "Message": "Access Denied"},
    "ResponseMetadata": {
        "RequestId": "QG12NMTNXA6GDVMV",
        "HostId": "W14+vd5H4T7DMdIVU021heCy2PKiFGhi/air1Iut/S6ORbti5Zdf+gBSJ7FDrIOL08tbbkrkOHE=",
        "HTTPStatusCode": 403,
        "HTTPHeaders": {
            "x-amz-bucket-region": "ap-southeast-2",
            "x-amz-request-id": "QG12NMTNXA6GDVMV",
            "x-amz-id-2": "W14+vd5H4T7DMdIVU021heCy2PKiFGhi/air1Iut/S6ORbti5Zdf+gBSJ7FDrIOL08tbbkrkOHE=",
            "content-type": "application/xml",
            "transfer-encoding": "chunked",
            "date": "Thu, 02 Feb 2023 01:46:47 GMT",
            "server": "AmazonS3",
        },
        "RetryAttempts": 0,
    },
}


def test_index_redirects_to_interface(testclient: TestClient):
    response = testclient.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["Location"] == "/ui"


def test_css_stylesheet_exists(testclient: TestClient):
    response = testclient.get("/static/style.css")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/css; charset=utf-8"


def test_error_handler_returns_json_response():
    response = generic_error_response(ValueError("Hello"))
    assert response.status_code == 500
    jsondata = json.loads(response.body.decode())
    assert jsondata == {
        "error": "ValueError",
        "detail": "-",
        "request_id": "",
        "traceback": ["NoneType: None", ""],
    }


def test_error_handler_responds_with_json_for_starlette_exceptions():
    response = generic_error_response(HTTPException(429, "Too Many Requests!"))
    assert response.status_code == 429
    jsondata = json.loads(response.body.decode())
    assert jsondata == {
        "error": "HTTPException",
        "detail": "Too Many Requests!",
        "request_id": "",
        "traceback": ["NoneType: None", ""],
    }


def test_error_handler_returns_with_json_for_botocore_expcetions():
    error = ClientError(_S3_RESPONSE, "ListObjects")
    assert str(error) == _S3_ERROR_MSG
    response = generic_error_response(error)
    jsondata = json.loads(response.body.decode())
    assert jsondata == {
        "error": "ClientError",
        "detail": {
            "message": _S3_ERROR_MSG,
            "operation": "ListObjects",
            "response": _S3_RESPONSE,
        },
        "request_id": "",
        "traceback": ["NoneType: None", ""],
    }
