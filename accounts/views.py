from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm, ProfileUpdateForm

class LoginView(auth_views.LoginView):
    authentication_form = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

class LogoutView(auth_views.LogoutView):
    pass


@login_required
def profile(request):
    form = ProfileUpdateForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil Anda berhasil diperbarui.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
