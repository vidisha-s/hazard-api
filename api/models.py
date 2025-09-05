from django.db import models
from django.contrib.auth.models import User


# A profile model to extend the default Django user and store their role.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Define roles for the platform.
    CITIZEN = 'citizen'
    OFFICIAL = 'official'
    ANALYST = 'analyst'
    ROLES = [
        (CITIZEN, 'Citizen'),
        (OFFICIAL, 'Official'),
        (ANALYST, 'Analyst'),
    ]
    role = models.CharField(max_length=20, choices=ROLES, default=CITIZEN)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


# Model to store a crowdsourced hazard report.
class HazardReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    description = models.TextField()

    # Location stored as lat/lon
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    # Optional media
    media_url = models.URLField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # Verification status
    VERIFIED = 'verified'
    UNVERIFIED = 'unverified'
    STATUS_CHOICES = [
        (VERIFIED, 'Verified'),
        (UNVERIFIED, 'Unverified'),
    ]
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=UNVERIFIED)

    def __str__(self):
        return f"Report by {self.user.username} at ({self.latitude}, {self.longitude})"


# A model to represent social media posts about hazards.
class SocialMediaPost(models.Model):
    platform = models.CharField(max_length=50)
    text_content = models.TextField()
    social_media_user = models.CharField(max_length=100)

    created_at = models.DateTimeField()  # Use auto_now_add=True if only local ingestion
    post_url = models.URLField(unique=True)
    extracted_keywords = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.platform} post by {self.social_media_user}"
