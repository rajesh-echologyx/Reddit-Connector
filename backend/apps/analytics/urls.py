from django.urls import path

from . import views

urlpatterns = [
    path("analytics/summary/", views.analytics_summary, name="analytics-summary"),
    path("analytics/funnel/", views.analytics_funnel, name="analytics-funnel"),
]
