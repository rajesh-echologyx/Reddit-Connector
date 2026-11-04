from django.urls import path

from . import views

urlpatterns = [
    path("auth/csrf/", views.csrf, name="auth-csrf"),
    path("auth/login/", views.login_view, name="auth-login"),
    path("auth/logout/", views.logout_view, name="auth-logout"),
    path("auth/me/", views.me, name="auth-me"),
    path("auth/bootstrap/", views.bootstrap, name="auth-bootstrap"),
    path("health/", views.health, name="health"),
    path("health/ready/", views.health_ready, name="health-ready"),
]
