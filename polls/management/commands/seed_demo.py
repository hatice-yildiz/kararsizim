from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from polls.models import Option, Poll, Vote

# Yalnızca yerel SQLite'ta deneme içindir. Gerçek veritabanında çalışmaz.
DEMO_EMAIL = "demo@example.com"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "Demo-Deneme-2026"


class Command(BaseCommand):
    help = "Yerel SQLite veritabanına demo kullanıcı ve örnek anketler ekler (giriş: demo@example.com)."

    def handle(self, *args, **options):
        if not settings.DEBUG or connection.vendor != "sqlite":
            raise CommandError("seed_demo yalnızca DEBUG açıkken ve yerel SQLite'ta çalışır.")
        User = get_user_model()
        demo, _ = User.objects.get_or_create(username=DEMO_USERNAME, defaults={"email": DEMO_EMAIL})
        demo.set_password(DEMO_PASSWORD)
        demo.save()
        other, _ = User.objects.get_or_create(username="mehmet", defaults={"email": "mehmet@example.com"})
        other.set_unusable_password()
        other.save()

        if Poll.objects.exists():
            self.stdout.write("Anketler zaten var, atlandı.")
        else:
            self._poll(demo, "Bugün sinemaya mı gitsem, yemeğe mi?", ["Sinema 🎬", "Yemek 🍝", "Evde kal 🛋️"],
                       [0, 0, 0, 1, 1, 2], "Hafta sonu için plan yapıyorum, kararsız kaldım.")
            self._poll(other, "Hangi telefonu alsam?", ["iPhone", "Samsung", "Xiaomi", "Pixel"], [1, 1, 0])
            self._poll(demo, "Çay mı kahve mi?", ["Çay", "Kahve"], [])
        self.stdout.write(self.style.SUCCESS(f"Hazır. Giriş e-postası: {DEMO_EMAIL}  (parola bu dosyada: {__file__})"))

    def _poll(self, user, question, options, votes, description=""):
        poll = Poll.objects.create(question=question, description=description, created_by=user)
        opts = [Option.objects.create(poll=poll, text=t, order=i) for i, t in enumerate(options, 1)]
        for n, idx in enumerate(votes):
            Vote.objects.create(poll=poll, option=opts[idx], voter_key=f"a:seed-{poll.pk}-{n}")
