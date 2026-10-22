from rest_framework.routers import SimpleRouter

from .views import CommentViewSet

app_name = "comments"

router = SimpleRouter()
router.register("", CommentViewSet, basename="comment")

urlpatterns = router.urls
