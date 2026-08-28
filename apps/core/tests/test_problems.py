import json

from django.test import RequestFactory
from ninja.errors import HttpError, ValidationError

from apps.core.problems import PROBLEM_MEDIA_TYPE, VALIDATION_PROBLEM_TYPE
from config.urls import api


def response_json(response) -> dict:
    return json.loads(response.content)


def test_validation_errors_follow_problem_details() -> None:
    request = RequestFactory().post("/api/v1/news")
    error = ValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "title"),
                "msg": "Field required",
                "input": {},
            }
        ]
    )

    response = api.on_exception(request, error)

    assert response.status_code == 422
    assert response["Content-Type"] == PROBLEM_MEDIA_TYPE
    assert response_json(response) == {
        "type": VALIDATION_PROBLEM_TYPE,
        "title": "Request validation failed",
        "status": 422,
        "detail": "One or more request fields are invalid.",
        "instance": "/api/v1/news",
        "errors": [
            {
                "pointer": "/body/title",
                "code": "missing",
                "detail": "Field required",
            }
        ],
    }


def test_http_errors_follow_problem_details() -> None:
    request = RequestFactory().get("/api/v1/private")

    response = api.on_exception(request, HttpError(403, "Forbidden"))

    assert response.status_code == 403
    assert response["Content-Type"] == PROBLEM_MEDIA_TYPE
    assert response_json(response) == {
        "type": "about:blank",
        "title": "Forbidden",
        "status": 403,
        "detail": "Forbidden",
        "instance": "/api/v1/private",
    }


def test_unknown_api_route_returns_problem_details(client) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response["Content-Type"] == PROBLEM_MEDIA_TYPE
    assert response_json(response)["instance"] == "/api/v1/does-not-exist"


def test_method_not_allowed_returns_problem_details(client) -> None:
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    assert response["Content-Type"] == PROBLEM_MEDIA_TYPE
    assert response["Allow"] == "GET"


def test_internal_errors_hide_exception_details(caplog) -> None:
    request = RequestFactory().get("/api/v1/news")

    response = api.on_exception(request, RuntimeError("sensitive database details"))

    assert response.status_code == 500
    assert response["Content-Type"] == PROBLEM_MEDIA_TYPE
    assert "sensitive database details" not in response.content.decode()
    assert "sensitive database details" in caplog.text
