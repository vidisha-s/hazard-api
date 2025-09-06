from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import UserProfileViewSet, HazardReportViewSet

router = DefaultRouter()
router.register(r'userprofiles', UserProfileViewSet)
router.register(r'hazards', HazardReportViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('token/', obtain_auth_token),
]