import logging
from http import HTTPStatus
from typing import Any

from django.http import Http404, HttpRequest, JsonResponse
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError, ValidationError

PROBLEM_MEDIA_TYPE = "application/problem+json"
VALIDATION_PROBLEM_TYPE = "urn:npca:problem:validation-error"

logger = logging.getLogger(__name__)


class ProblemDetails(Schema):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


class ValidationIssue(Schema):
    pointer: str
    code: str
    detail: str


class ValidationProblem(ProblemDetails):
    errors: list[ValidationIssue]


def status_title(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return f"HTTP {status} error"


def problem_response(problem: ProblemDetails) -> JsonResponse:
    return JsonResponse(
        problem.model_dump(exclude_none=True),
        status=problem.status,
        content_type=PROBLEM_MEDIA_TYPE,
    )


def generic_problem(request: HttpRequest, status: int, detail: str) -> JsonResponse:
    return problem_response(
        ProblemDetails(
            title=status_title(status),
            status=status,
            detail=detail,
            instance=request.path,
        )
    )


def _json_pointer(error: dict[str, Any]) -> str:
    location = error.get("loc", ())
    if not isinstance(location, (list, tuple)):
        location = (location,)

    escaped = [str(item).replace("~", "~0").replace("/", "~1") for item in location]
    return f"/{'/'.join(escaped)}" if escaped else ""


def validation_error_handler(request: HttpRequest, exc: ValidationError) -> JsonResponse:
    errors = [
        ValidationIssue(
            pointer=_json_pointer(error),
            code=str(error.get("type", "invalid")),
            detail=str(error.get("msg", "Invalid value.")),
        )
        for error in exc.errors
    ]
    return problem_response(
        ValidationProblem(
            type=VALIDATION_PROBLEM_TYPE,
            title="Request validation failed",
            status=422,
            detail="One or more request fields are invalid.",
            instance=request.path,
            errors=errors,
        )
    )


def http_error_handler(request: HttpRequest, exc: HttpError) -> JsonResponse:
    return generic_problem(request, exc.status_code, str(exc))


def not_found_handler(request: HttpRequest, exc: Http404) -> JsonResponse:
    return generic_problem(request, 404, "The requested resource was not found.")


def internal_error_handler(request: HttpRequest, exc: Exception) -> JsonResponse:
    logger.error(
        "Unhandled API exception on %s",
        request.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return generic_problem(request, 500, "An unexpected error occurred.")


def register_problem_handlers(api: NinjaAPI) -> None:
    api.add_exception_handler(ValidationError, validation_error_handler)
    api.add_exception_handler(HttpError, http_error_handler)
    api.add_exception_handler(Http404, not_found_handler)
    api.add_exception_handler(Exception, internal_error_handler)
