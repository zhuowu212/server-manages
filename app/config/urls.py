from django.urls import include, path

from .health import live, ready

urlpatterns = [
    path("", include("accounts.ui_urls")),
    path("", include("assets.ui_urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("assets.urls")),
    path("health/live", live), path("health/ready", ready),
]
