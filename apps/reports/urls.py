from django.urls import path

from .views import DashboardView, OverdueReportView

app_name = "reports"

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("overdue/", OverdueReportView.as_view(), name="overdue"),
]
