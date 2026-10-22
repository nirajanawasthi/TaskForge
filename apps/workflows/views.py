from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.mixins import ProjectScopedMixin
from apps.tasks.models import Task
from apps.tasks.serializers import TaskSerializer

from .serializers import TransitionSerializer
from .services import apply_transition


class TaskTransitionView(ProjectScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=TransitionSerializer, responses={200: TaskSerializer})
    def post(self, request, *args, **kwargs):
        task = get_object_or_404(
            Task.objects.filter(project=self.project), pk=kwargs["task_pk"]
        )
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = apply_transition(
            task=task,
            user=request.user,
            role=self.requesting_membership.role,
            action=serializer.validated_data["action"],
        )
        return Response(TaskSerializer(task).data)
