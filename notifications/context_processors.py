from .models import WebNotification


def web_notifications(request):
    if not getattr(request.user, "is_authenticated", False):
        return {"web_notifications": [], "web_notification_unread_count": 0}

    queryset = WebNotification.objects.filter(recipient=request.user)
    return {
        "web_notifications": list(queryset[:8]),
        "web_notification_unread_count": queryset.filter(is_read=False).count(),
    }
