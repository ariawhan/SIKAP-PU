from functools import wraps
from django.core.exceptions import PermissionDenied

def super_admin_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_super_admin:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped
