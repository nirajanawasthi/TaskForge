from django.urls import path

from .views import TaskTransitionView

app_name = "workflows"

urlpatterns = [
    path("transition/", TaskTransitionView.as_view(), name="task-transition"),
]
