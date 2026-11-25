from django.urls import path
from .views import LoginView, LogoutView, profile
app_name = "accounts"
urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("profil/", profile, name="profile"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
