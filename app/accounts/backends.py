from django.contrib.auth.backends import BaseBackend

from .models import User
from .passwords import verify_password


class LocalBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not isinstance(username, str) or not isinstance(password, str):
            return None
        user = User.objects.filter(username_key=username.strip().casefold(), active=True).first()
        if user and verify_password(user.password_hash, password):
            return user
        return None

    def get_user(self, user_id):
        return User.objects.filter(pk=user_id, active=True).first()
