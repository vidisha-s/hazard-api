from rest_framework import viewsets, permissions
from .models import UserProfile, HazardReport
from .serializers import UserProfileSerializer, HazardReportSerializer

# User Profile ViewSet
class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    
    def perform_create(self, serializer):
        # Automatically attach logged-in user to the profile
        serializer.save(user=self.request.user)


# Hazard Report ViewSet
class HazardReportViewSet(viewsets.ModelViewSet):
    queryset = HazardReport.objects.all()
    serializer_class = HazardReportSerializer
    