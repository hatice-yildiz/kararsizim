from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import EmailLoginForm, RegisterForm


class GuestLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, "Giriş yaptın. Hoş geldin!")
        return super().form_valid(form)


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="accounts.backends.EmailBackend")
            messages.success(request, f"Hoş geldin, @{user.username}!")
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "Çıkış yaptın.")
    return redirect("home")
