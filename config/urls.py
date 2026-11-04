from django.contrib import admin
from django.urls import path

from accounts import views as account_views
from predictions import views as v

admin.site.site_header = "Tahmince Yönetim"
admin.site.site_title = "Tahmince"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Tahmin soruları
    path("", v.home, name="home"),
    path("soru/yeni/", v.question_create, name="question_create"),
    path("soru/<int:pk>/", v.question_detail, name="question_detail"),
    path("soru/<int:pk>/tahmin/", v.predict, name="predict"),
    path("soru/<int:pk>/duzenle/", v.question_edit, name="question_edit"),
    path("soru/<int:pk>/sil/", v.question_delete, name="question_delete"),
    path("soru/<int:pk>/sonuc/", v.question_resolve, name="question_resolve"),
    path("soru/<int:pk>/iptal/", v.question_cancel, name="question_cancel"),
    path("tahminlerim/", v.my_predictions, name="my_predictions"),
    path("sorularim/", v.my_questions, name="my_questions"),
    path("puan-tablosu/", v.leaderboard, name="leaderboard"),
    # Üyelik
    path("kayit/", account_views.register, name="register"),
    path("giris/", account_views.GuestLoginView.as_view(), name="login"),
    path("cikis/", account_views.logout_view, name="logout"),
]
