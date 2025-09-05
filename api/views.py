from rest_framework import viewsets
from .models import UserProfile, HazardReport
from .serializers import UserProfileSerializer, HazardReportSerializer

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

class HazardReportViewSet(viewsets.ModelViewSet):
    queryset = HazardReport.objects.all()
    serializer_class = HazardReportSerializer