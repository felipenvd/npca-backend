from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .problems import PROBLEM_MEDIA_TYPE, generic_problem


class ApiProblemDetailsMiddleware:
    api_prefix = "/api/v1/"
    health_path = "/api/v1/health"
    preserved_headers = ("Allow", "Retry-After", "WWW-Authenticate")

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        if not self._should_replace(request, response):
            return response

        problem = generic_problem(request, response.status_code, self._detail(response.status_code))
        for header in self.preserved_headers:
            if header in response:
                problem[header] = response[header]
        return problem

    def _should_replace(self, request: HttpRequest, response: HttpResponse) -> bool:
        return (
            request.path.startswith(self.api_prefix)
            and not (request.path == self.health_path and response.status_code == 503)
            and response.status_code >= 400
            and not response.get("Content-Type", "").startswith(PROBLEM_MEDIA_TYPE)
        )

    @staticmethod
    def _detail(status: int) -> str:
        details = {
            404: "The requested resource was not found.",
            405: "The HTTP method is not allowed for this resource.",
        }
        return details.get(
            status,
            "The server could not process the request."
            if status >= 500
            else "The request could not be processed.",
        )
