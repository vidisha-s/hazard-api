from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, HazardReport


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="user", write_only=True
    )

    class Meta:
        model = UserProfile
        fields = ["id", "user", "user_id", "role"]


class HazardReportSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="user", write_only=True, required=False
    )

    class Meta:
        model = HazardReport
        fields = [
            "id",
            "user",
            "user_id",
            "description",
            "latitude",
            "longitude",
            "media_url",
            "status",
            "created_at",
        ]
        extra_kwargs = {
            "created_at": {"read_only": True},
            "status": {"required": False},
        }

    def create(self, validated_data):
        # auto-assign logged-in user if user_id is not given
        if "user" not in validated_data:
            validated_data["user"] = self.context["request"].user
        return super().create(validated_data)
