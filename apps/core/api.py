from typing import Literal

from django.db import connection
from django.db.utils import DatabaseError
from ninja import Router, Schema
from ninja.responses import Status

router = Router(tags=["system"])


class HealthOk(Schema):
    status: Literal["ok"]
    database: Literal["ok"]


class HealthUnavailable(Schema):
    status: Literal["unavailable"]
    database: Literal["error"]


@router.get(
    "/health",
    auth=None,
    response={200: HealthOk, 503: HealthUnavailable},
    summary="Verifica a aplicação e o banco de dados",
)
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return Status(503, {"status": "unavailable", "database": "error"})

    return {"status": "ok", "database": "ok"}
