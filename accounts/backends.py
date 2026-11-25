from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identity = (username or kwargs.get("email") or "").strip()
        if not identity or not password: return None
        User = get_user_model()
        try: user = User.objects.get(Q(username__iexact=identity) | Q(email__iexact=identity))
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            User().set_password(password)
            return None
        return user if user.check_password(password) and self.user_can_authenticate(user) else None
