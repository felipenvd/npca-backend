from unittest.mock import patch

import pytest
from django.db.utils import OperationalError


@pytest.mark.django_db
def test_health_returns_ok(client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_health_hides_database_errors(client) -> None:
    with patch("apps.core.api.connection.cursor", side_effect=OperationalError):
        response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response["Content-Type"].startswith("application/json")
    assert response.json() == {"status": "unavailable", "database": "error"}
