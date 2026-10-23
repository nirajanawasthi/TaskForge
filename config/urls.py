from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

TASK_URL = "api/organizations/<int:organization_pk>/projects/<int:project_pk>/tasks/"

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="app"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path(TASK_URL + "<int:task_pk>/comments/", include("apps.comments.urls")),
    path(TASK_URL + "<int:task_pk>/activity/", include("apps.activity_logs.urls")),
    path(TASK_URL + "<int:task_pk>/", include("apps.workflows.urls")),
    path(TASK_URL, include("apps.tasks.urls")),
    path(
        "api/organizations/<int:organization_pk>/projects/",
        include("apps.projects.urls"),
    ),
    path(
        "api/organizations/<int:organization_pk>/reports/",
        include("apps.reports.urls"),
    ),
    path("api/organizations/", include("apps.organizations.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
