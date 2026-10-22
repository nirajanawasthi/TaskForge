from rest_framework.routers import SimpleRouter

from .views import ActivityViewSet

app_name = "activity_logs"

router = SimpleRouter()
router.register("", ActivityViewSet, basename="activity")

urlpatterns = router.urls
