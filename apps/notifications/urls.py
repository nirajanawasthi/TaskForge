from rest_framework.routers import SimpleRouter

from .views import NotificationViewSet

app_name = "notifications"

router = SimpleRouter()
router.register("", NotificationViewSet, basename="notification")

urlpatterns = router.urls
