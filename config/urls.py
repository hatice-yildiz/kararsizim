from django.contrib import admin
from django.urls import path

from accounts import views as account_views
from polls import views as poll_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", poll_views.home, name="home"),
    path("anket/yeni/", poll_views.poll_create, name="poll_create"),
    path("anket/<int:pk>/", poll_views.poll_detail, name="poll_detail"),
    path("anket/<int:pk>/oy/", poll_views.poll_vote, name="poll_vote"),
    path("anket/<int:pk>/sil/", poll_views.poll_delete, name="poll_delete"),
    path("anketlerim/", poll_views.my_polls, name="my_polls"),
    path("kayit/", account_views.register, name="register"),
    path("giris/", account_views.GuestLoginView.as_view(), name="login"),
    path("cikis/", account_views.logout_view, name="logout"),
]
