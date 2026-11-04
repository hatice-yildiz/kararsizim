from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from predictions import services
from predictions.models import Choice, Prediction, Question

# Yalnızca yerel SQLite'ta görsel deneme içindir; DEBUG kapalıyken ya da PostgreSQL'de çalışmaz.
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "Demo-Deneme-2026"


class Command(BaseCommand):
    help = "Yerel SQLite'a demo kullanıcılar ve her durumda örnek tahmin soruları ekler."

    def handle(self, *args, **options):
        if not settings.DEBUG or connection.vendor != "sqlite":
            raise CommandError("seed_demo yalnızca DEBUG açıkken ve yerel SQLite'ta çalışır.")
        User = get_user_model()
        if Question.objects.exists():
            self.stdout.write("Zaten veri var, atlandı.")
            return
        demo, _ = User.objects.get_or_create(username="demo", defaults={"email": DEMO_EMAIL})
        demo.set_password(DEMO_PASSWORD)
        demo.save()
        people = {n: User.objects.get_or_create(username=n, defaults={"email": f"{n}@example.com"})[0]
                  for n in ("ayse", "mehmet", "zeynep", "can")}
        for u in people.values():
            u.set_password(DEMO_PASSWORD)
            u.save()

        def q(owner, title, choices, hours, category, criteria="Resmi açıklamalar esas alınır."):
            obj = Question.objects.create(title=title, description="Örnek bir tahmin sorusu.", resolution_criteria=criteria,
                                          category=category, created_by=owner, closes_at=timezone.now() + timedelta(hours=hours))
            for i, t in enumerate(choices, start=1):
                Choice.objects.create(question=obj, text=t, position=i)
            return obj

        def guess(question, user, idx):
            Prediction.objects.create(question=question, user=user, choice=question.choices.all()[idx])

        def age(obj):  # süresi dolmuş hâle getir
            Question.objects.filter(pk=obj.pk).update(created_at=timezone.now() - timedelta(days=3), closes_at=timezone.now() - timedelta(hours=2))

        derby = q(people["ayse"], "Hafta sonu derbisini kim kazanır?", ["Ev sahibi", "Deplasman", "Beraberlik"], 52, "spor", "90 dakika sonundaki resmi skor.")
        for name, i in (("mehmet", 0), ("zeynep", 0), ("can", 2), ("demo", 1)):
            guess(derby, people.get(name, demo), i)
        phone = q(people["mehmet"], "Yeni amiral gemisi telefon bu ay tanıtılır mı?", ["Evet", "Hayır"], 130, "teknoloji")
        guess(phone, people["ayse"], 0)
        q(people["zeynep"], "Bu hafta sonu İstanbul'da yağmur yağar mı?", ["Evet", "Hayır"], 5, "gunluk", "Meteoroloji genel müdürlüğü gözlemi.")
        q(people["can"], "Yılın dizisi ödülünü hangi yapım alır?", ["Dizi A", "Dizi B", "Dizi C", "Dizi D"], 400, "eglence")
        q(demo, "Benim sorum: kahve mi çay mı?", ["Kahve", "Çay"], 90, "diger")

        pending = q(people["ayse"], "Final maçında ilk gol kimden gelir?", ["Birinci takım", "İkinci takım"], 2, "spor")
        guess(pending, people["mehmet"], 0)
        guess(pending, demo, 1)
        age(pending)

        done = q(people["mehmet"], "Yeni oyun konsolu duyurulur mu?", ["Evet", "Hayır"], 2, "teknoloji")
        for name, i in (("ayse", 0), ("zeynep", 0), ("can", 1), ("demo", 0)):
            guess(done, people.get(name, demo), i)
        age(done)
        services.resolve_question(people["mehmet"], done.pk, done.choices.first().pk,
                                  "Şirket etkinliğinde yeni konsol resmen tanıtıldı.", "https://example.com/haber")

        cancelled = q(people["can"], "Konserin biletleri tükenir mi?", ["Evet", "Hayır"], 3, "eglence")
        guess(cancelled, people["ayse"], 0)
        age(cancelled)
        services.cancel_question(people["can"], cancelled.pk, "Konser ertelendi, sonuç belirlenemiyor.")
        self.stdout.write(self.style.SUCCESS(f"Hazır. Giriş: {DEMO_EMAIL} ya da 'demo' (parola bu dosyada: {__file__})"))
