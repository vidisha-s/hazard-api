from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, HazardReport


# -------------------------
# User Serializer
# -------------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


# -------------------------
# User Profile Serializer
# -------------------------
class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)  # Nested display

    class Meta:
        model = UserProfile
        fields = ["id", "user", "role", "phone", "address"]


# -------------------------
# Hazard Report Serializer
# -------------------------
class HazardReportSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)  # Show user details

    class Meta:
        model = HazardReport
        fields = [
            "id",
            "description",
            "latitude",
            "longitude",
            "media_url",
            "status",
            "created_at",
            "user",
        ]
        read_only_fields = ["id", "created_at", "user", "status"]

    # ✅ Assign logged-in user automatically on create
    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["user"] = request.user
        return super().create(validated_data)

    # ✅ Ensure only the owner can update
    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and instance.user != request.user:
            raise serializers.ValidationError(
                {"error": "You can only update your own reports."}
            )
        return super().update(instance, validated_data)

            