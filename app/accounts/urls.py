from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.login_view), path("auth/logout", views.logout_view),
    path("auth/me", views.me_view), path("auth/password", views.password_view),
    path("users", views.users_collection_view),
    path("users/<uuid:user_id>", views.user_update_view), path("users/<uuid:user_id>/change-preview", views.user_preview_view),
    path("users/<uuid:user_id>/reset-password", views.user_reset_password_view),
]
