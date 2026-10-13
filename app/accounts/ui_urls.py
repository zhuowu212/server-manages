from django.urls import path

from . import ui_views

urlpatterns = [
    path("", ui_views.home_view, name="home"),
    path("login", ui_views.login_page, name="login_page"),
    path("logout", ui_views.logout_page, name="logout_page"),
    path("password", ui_views.password_page, name="password_page"),
    path("users", ui_views.users_page, name="users_page"),
]
