from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.ProfileDetailView.as_view(), name="profile-detail"),
    path(
        "writing-samples/",
        views.WritingSampleListCreateView.as_view(),
        name="writing-samples-list",
    ),
    path(
        "writing-samples/<uuid:pk>/",
        views.WritingSampleDetailView.as_view(),
        name="writing-samples-detail",
    ),
]
