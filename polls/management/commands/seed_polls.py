from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from polls.models import Option, Poll

SYSTEM_USERNAME = "kararsizim"
SYSTEM_EMAIL = "sistem@kararsizim.invalid"  # .invalid: gerçek bir adres değil, kimse bu hesaba giremez

# (soru, açıklama, seçenekler) — hepsi 2-5 seçenek, Türkçe.
SAMPLE_POLLS = [
    ("Bu akşam ne yapsam?", "Hafta içi, yorgunum ama evde de sıkılırım.",
     ["Sinemaya git 🎬", "Arkadaşlarla yemek 🍝", "Evde dizi maratonu 🛋️", "Yürüyüşe çık 🚶"]),
    ("Çay mı kahve mi?", "",
     ["Çay ☕", "Türk kahvesi", "Filtre kahve"]),
    ("Tatil için hangisi?", "Bir hafta izin var, bütçe orta.",
     ["Deniz ve güneş 🏖️", "Doğa ve yürüyüş 🏔️", "Şehir gezisi 🏙️", "Evde dinlen 😴"]),
    ("Yeni telefon alırken en çok neye bakmalıyım?", "",
     ["Kamera 📷", "Pil ömrü 🔋", "Fiyat 💸", "Marka"]),
    ("Sabah mı gece mi çalışmak daha verimli?", "",
     ["Sabah erkenden 🌅", "Gece geç saatte 🌙"]),
    ("İlk işte hangisini seçmeliyim?", "İki teklifim var, kararsız kaldım.",
     ["Yüksek maaş, yoğun tempo", "Orta maaş, rahat tempo", "Daha düşük maaş, çok öğreneceğim yer"]),
    ("Hafta sonu brunch için hangi mekan?", "",
     ["Boğaz manzaralı kafe", "Mahalledeki küçük fırın", "Evde kendi brunch'ım"]),
    ("Kitap mı film mi?", "Bu hafta sonu bir tanesini bitirmek istiyorum.",
     ["Kitap 📚", "Film 🎥"]),
    ("Evcil hayvan alsam hangisi?", "",
     ["Kedi 🐱", "Köpek 🐶", "Kuş 🐦", "Balık 🐟", "Şimdilik hiçbiri"]),
    ("Spora hangi saatte başlasam?", "",
     ["Sabah işten önce", "Öğle arasında", "Akşam işten sonra"]),
]


class Command(BaseCommand):
    help = "Herkesin gördüğü örnek anketleri 'kararsizim' sistem hesabı adına ekler. Tekrar çalıştırmak kopya üretmez."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        system, created = User.objects.get_or_create(
            username=SYSTEM_USERNAME, defaults={"email": SYSTEM_EMAIL}
        )
        if created or system.has_usable_password():
            system.set_unusable_password()  # kimse bu hesapla giriş yapamaz
            system.save()

        added = 0
        for question, description, options in SAMPLE_POLLS:
            if Poll.objects.filter(created_by=system, question=question).exists():
                continue
            poll = Poll.objects.create(question=question, description=description, created_by=system)
            Option.objects.bulk_create(
                Option(poll=poll, text=text, order=i) for i, text in enumerate(options, start=1)
            )
            added += 1
        self.stdout.write(self.style.SUCCESS(
            f"{added} örnek anket eklendi, {len(SAMPLE_POLLS) - added} zaten vardı. "
            f"Sistem hesabı: @{SYSTEM_USERNAME}"
        ))
