from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path
from ninja import NinjaAPI

from apps.core.api import router as core_router
from apps.core.problems import register_problem_handlers
from apps.news.api import router as news_router
from apps.projects.api import router as projects_router
from apps.researchers.api import router as researchers_router

docs_decorator = staff_member_required if settings.NINJA_DOCS_REQUIRE_STAFF else None

api = NinjaAPI(
    title="NPCA API",
    version="1.0.0",
    description="API pública do Núcleo de Pesquisa em Computação Aplicada.",
    docs_decorator=docs_decorator,
    urls_namespace="npca-api-v1",
)
register_problem_handlers(api)
api.add_router("", core_router)
api.add_router("/news", news_router)
api.add_router("/researchers", researchers_router)
api.add_router("/projects", projects_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
