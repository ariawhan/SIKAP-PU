from django.urls import path
from . import views
app_name = "dashboard"
urlpatterns = [
    path("", views.index, name="index"),
    path("reminder/<int:pk>/kirim/", views.send_reminder, name="send_reminder"),
    path("pengguna/", views.users, name="users"),
]
