"""Profile + writing-sample API."""

from __future__ import annotations

from rest_framework import generics, permissions

from .models import WritingSample
from .serializers import UserProfileSerializer, WritingSampleSerializer
from .services import get_or_create_profile


class ProfileDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/profile/ — auto-creates empty profile on first access."""

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_or_create_profile(self.request.user)


class WritingSampleListCreateView(generics.ListCreateAPIView):
    serializer_class = WritingSampleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WritingSample.objects.filter(user=self.request.user)


class WritingSampleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WritingSampleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WritingSample.objects.filter(user=self.request.user)
