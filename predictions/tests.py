from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from . import services
from .models import Choice, Prediction, Question, Status

User = get_user_model()
PASSWORD = "GucluSifre#2026"


def make_user(name, email=None):
    return User.objects.create_user(username=name, email=email or f"{name}@example.com", password=PASSWORD)


def make_question(owner, title="Maç kim kazanır?", choices=("A takımı", "B takımı"), hours=24, category="spor"):
    q = Question.objects.create(
        title=title, description="Açıklama", resolution_criteria="Resmi skor", category=category,
        created_by=owner, closes_at=timezone.now() + timedelta(hours=hours),
    )
    for i, text in enumerate(choices, start=1):
        Choice.objects.create(question=q, text=text, position=i)
    return q


def _without_triggers(fn):
    """Test verisini hazırlarken tetikleyicileri (PostgreSQL) işlem içinde geçici kapatır; SQLite'ta doğrudan çalışır."""
    if connection.vendor != "postgresql":
        return fn()
    from django.db import transaction
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SET LOCAL session_replication_role = replica")
        try:
            return fn()
        finally:
            cur.execute("SET LOCAL session_replication_role = origin")


def close(q):
    """Soruyu geçmişe taşır (kapanış < şimdi); created_at < closes_at kuralı korunur."""
    def go():
        Question.objects.filter(pk=q.pk).update(
            created_at=timezone.now() - timedelta(days=2), closes_at=timezone.now() - timedelta(hours=1)
        )
    _without_triggers(go)
    q.refresh_from_db()
    return q


def force_prediction(**kwargs):
    """Kuralları atlayarak ham tahmin kaydı ekler (yalnızca test verisi hazırlamak için)."""
    return _without_triggers(lambda: Prediction.objects.create(**kwargs))


def predict(client, q, choice):
    return client.post(reverse("predict", args=[q.pk]), {"choice": choice.pk}, follow=True)


# ============================================================================ durumlar
class StatusTests(TestCase):
    def setUp(self):
        self.owner = make_user("sahip")

    def test_four_visible_states(self):
        open_q = make_question(self.owner)
        pending = close(make_question(self.owner))
        resolved = close(make_question(self.owner))
        cancelled = make_question(self.owner)
        services.resolve_question(self.owner, resolved.pk, resolved.choices.first().pk, "Bitti gerçekten")
        services.cancel_question(self.owner, cancelled.pk, "Sonuç belirlenemedi artık")
        for q in (open_q, pending, resolved, cancelled):
            q.refresh_from_db()
        self.assertEqual(open_q.display_status, "open")
        self.assertEqual(pending.display_status, "pending")
        self.assertEqual(resolved.display_status, "resolved")
        self.assertEqual(cancelled.display_status, "cancelled")
        self.assertEqual(set(Question.objects.accepting()), {open_q})
        self.assertEqual(set(Question.objects.awaiting()), {pending})
        self.assertEqual(set(Question.objects.finished()), {resolved, cancelled})


# ============================================================================ oluşturma
class CreateQuestionTests(TestCase):
    url = "/soru/yeni/"

    def setUp(self):
        self.user = make_user("ayse")
        self.future = (timezone.localtime() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")

    def data(self, **kw):
        d = {"title": "Yarın yağmur yağar mı?", "description": "", "resolution_criteria": "Meteoroloji verisi",
             "category": "gunluk", "closes_at": self.future, "choice_1": "Evet", "choice_2": "Hayır"}
        d.update(kw)
        return d

    def test_guest_must_login(self):
        self.assertRedirects(self.client.get(self.url), "/giris/?next=/soru/yeni/")
        self.client.post(self.url, self.data())
        self.assertEqual(Question.objects.count(), 0)

    def test_create_with_2_to_4_choices(self):
        self.client.force_login(self.user)
        for n in (2, 3, 4):
            extra = {f"choice_{i}": f"Seçenek {i}" for i in range(1, n + 1)}
            r = self.client.post(self.url, self.data(title=f"Soru {n}", **extra))
            q = Question.objects.get(title=f"Soru {n}")
            self.assertRedirects(r, reverse("question_detail", args=[q.pk]))
            self.assertEqual(q.choices.count(), n)
            self.assertEqual(q.created_by, self.user)
            self.assertEqual(q.status, Status.OPEN)

    def test_fewer_than_two_choices_rejected(self):
        self.client.force_login(self.user)
        r = self.client.post(self.url, self.data(choice_2=""))
        self.assertContains(r, "En az 2 seçenek girmelisin.")
        self.assertEqual(Question.objects.count(), 0)

    def test_fifth_choice_is_ignored(self):
        self.client.force_login(self.user)
        self.client.post(self.url, self.data(choice_3="C", choice_4="D", choice_5="E"))
        self.assertEqual(Question.objects.get().choices.count(), 4)

    def test_duplicate_choices_rejected_case_and_space_insensitive(self):
        self.client.force_login(self.user)
        r = self.client.post(self.url, self.data(choice_1="Evet", choice_2="  evet "))
        self.assertContains(r, "Bu seçenek zaten eklenmiş.")
        self.assertEqual(Question.objects.count(), 0)

    def test_closing_must_be_in_the_future(self):
        self.client.force_login(self.user)
        past = (timezone.localtime() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        r = self.client.post(self.url, self.data(closes_at=past))
        self.assertContains(r, "Kapanış zamanı gelecekte olmalı.")
        soon = (timezone.localtime() + timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M")
        self.client.post(self.url, self.data(closes_at=soon))
        self.assertEqual(Question.objects.count(), 0)

    def test_invalid_or_missing_closing_rejected(self):
        self.client.force_login(self.user)
        r = self.client.post(self.url, self.data(closes_at="yarın"))
        self.assertContains(r, "Geçerli bir tarih ve saat gir.")
        r = self.client.post(self.url, self.data(closes_at=""))
        self.assertContains(r, "Kapanış zamanı zorunludur.")
        self.assertEqual(Question.objects.count(), 0)

    def test_browser_utc_value_wins_and_is_stored_in_utc(self):
        self.client.force_login(self.user)
        utc = (timezone.now() + timedelta(days=3)).replace(microsecond=0)
        self.client.post(self.url, self.data(closes_at="2000-01-01T00:00", closes_at_utc=utc.isoformat().replace("+00:00", "Z")))
        self.assertEqual(Question.objects.get().closes_at, utc)

    def test_required_fields_and_category(self):
        self.client.force_login(self.user)
        r = self.client.post(self.url, self.data(resolution_criteria=""))
        self.assertContains(r, "Sonucun nasıl belirleneceğini yazmalısın.")
        r = self.client.post(self.url, self.data(category="kumar"))
        self.assertContains(r, "Geçerli bir kategori seç.")
        r = self.client.post(self.url, self.data(title=""))
        self.assertContains(r, "Başlık zorunludur.")
        self.assertEqual(Question.objects.count(), 0)

    def test_all_five_categories_available(self):
        self.client.force_login(self.user)
        html = self.client.get(self.url).content.decode()
        for label in ["Spor", "Teknoloji", "Eğlence", "Günlük Hayat", "Diğer"]:
            self.assertIn(label, html)

    def test_input_preserved_on_error(self):
        self.client.force_login(self.user)
        r = self.client.post(self.url, self.data(choice_2="", title="Korunan başlık"))
        self.assertContains(r, "Korunan başlık")


# ============================================================================ tahmin yapma
class PredictTests(TestCase):
    def setUp(self):
        self.owner = make_user("sahip")
        self.u = make_user("ali")
        self.q = make_question(self.owner, choices=("A", "B", "C"))
        self.a, self.b, self.c = self.q.choices.all()

    def test_guest_cannot_predict(self):
        r = self.client.post(reverse("predict", args=[self.q.pk]), {"choice": self.a.pk})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/giris/", r["Location"])
        self.assertEqual(Prediction.objects.count(), 0)

    def test_member_predicts_once_and_sees_message(self):
        self.client.force_login(self.u)
        r = predict(self.client, self.q, self.a)
        self.assertContains(r, "Tahminin kaydedildi!")
        self.assertContains(r, "Senin tahminin")
        self.assertEqual(Prediction.objects.get().choice, self.a)

    def test_change_prediction_until_close_keeps_single_row(self):
        self.client.force_login(self.u)
        predict(self.client, self.q, self.a)
        r = predict(self.client, self.q, self.b)
        self.assertContains(r, "Tahminin güncellendi.")
        self.assertEqual(Prediction.objects.count(), 1)
        self.assertEqual(Prediction.objects.get().choice, self.b)

    def test_same_choice_again_changes_nothing(self):
        self.client.force_login(self.u)
        predict(self.client, self.q, self.a)
        r = predict(self.client, self.q, self.a)
        self.assertContains(r, "Zaten bu seçeneği seçmiştin.")
        self.assertEqual(Prediction.objects.count(), 1)

    def test_no_new_prediction_after_close(self):
        close(self.q)
        self.client.force_login(self.u)
        r = predict(self.client, self.q, self.a)
        self.assertContains(r, "Bu sorunun tahmin süresi doldu.")
        self.assertEqual(Prediction.objects.count(), 0)

    def test_no_change_after_close(self):
        self.client.force_login(self.u)
        predict(self.client, self.q, self.a)
        close(self.q)
        r = predict(self.client, self.q, self.b)
        self.assertContains(r, "Bu sorunun tahmin süresi doldu.")
        self.assertEqual(Prediction.objects.get().choice, self.a)

    def test_owner_cannot_predict_on_own_question(self):
        self.client.force_login(self.owner)
        r = predict(self.client, self.q, self.a)
        self.assertContains(r, "Kendi sorunuza tahmin yapamazsınız.")
        self.assertEqual(Prediction.objects.count(), 0)

    def test_invalid_and_foreign_choices_rejected(self):
        other = make_question(self.owner, title="Başka soru")
        foreign = other.choices.first()
        self.client.force_login(self.u)
        for bad in ["", "abc", "999999", "-1", str(foreign.pk)]:
            self.client.post(reverse("predict", args=[self.q.pk]), {"choice": bad})
        self.assertEqual(Prediction.objects.count(), 0)

    def test_cannot_predict_on_resolved_or_cancelled(self):
        resolved = close(make_question(self.owner, title="Bitti"))
        services.resolve_question(self.owner, resolved.pk, resolved.choices.first().pk, "Sonuç açıklandı")
        cancelled = make_question(self.owner, title="İptal")
        services.cancel_question(self.owner, cancelled.pk, "Belirlenemeyen sonuç")
        self.client.force_login(self.u)
        for q in (resolved, cancelled):
            predict(self.client, q, q.choices.first())
        self.assertEqual(Prediction.objects.count(), 0)

    def test_predict_requires_post(self):
        self.client.force_login(self.u)
        self.assertEqual(self.client.get(reverse("predict", args=[self.q.pk])).status_code, 405)

    def test_unknown_question_404(self):
        self.client.force_login(self.u)
        self.assertEqual(self.client.post(reverse("predict", args=[9999]), {"choice": 1}).status_code, 404)

    def test_distribution_counts_and_percentages_visible_to_guests(self):
        for i, ch in enumerate([self.a, self.a, self.b]):
            c = Client()
            c.force_login(make_user(f"u{i}"))
            predict(c, self.q, ch)
        r = self.client.get(reverse("question_detail", args=[self.q.pk]))
        by = {c.text: c for c in r.context["choices"]}
        self.assertEqual((by["A"].count, by["A"].percent), (2, 67))
        self.assertEqual((by["B"].count, by["B"].percent), (1, 33))
        self.assertEqual((by["C"].count, by["C"].percent), (0, 0))
        self.assertEqual(r.context["total"], 3)
        self.assertContains(r, "%67")

    def test_my_choice_is_marked(self):
        self.client.force_login(self.u)
        predict(self.client, self.q, self.b)
        r = self.client.get(reverse("question_detail", args=[self.q.pk]))
        self.assertEqual([c.text for c in r.context["choices"] if c.is_mine], ["B"])
        self.assertContains(r, "is-mine")


# ============================================================================ düzenleme / silme
class EditDeleteTests(TestCase):
    def setUp(self):
        self.owner = make_user("sahip")
        self.other = make_user("baska")
        self.q = make_question(self.owner)

    def edit_data(self, **kw):
        d = {"title": "Yeni başlık", "description": "Yeni açıklama", "resolution_criteria": "Yeni ölçüt",
             "category": "teknoloji", "closes_at": (timezone.localtime() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
             "choice_1": "X", "choice_2": "Y", "choice_3": "Z"}
        d.update(kw)
        return d

    def test_edit_everything_before_first_prediction(self):
        self.client.force_login(self.owner)
        r = self.client.post(reverse("question_edit", args=[self.q.pk]), self.edit_data())
        self.assertRedirects(r, reverse("question_detail", args=[self.q.pk]))
        self.q.refresh_from_db()
        self.assertEqual(self.q.title, "Yeni başlık")
        self.assertEqual([c.text for c in self.q.choices.all()], ["X", "Y", "Z"])
        self.assertEqual(self.q.category, "teknoloji")

    def test_core_fields_locked_after_first_prediction(self):
        make_user("ali")
        c = Client()
        c.force_login(User.objects.get(username="ali"))
        predict(c, self.q, self.q.choices.first())
        old_title, old_closes = self.q.title, self.q.closes_at
        old_choices = [x.text for x in self.q.choices.all()]
        self.client.force_login(self.owner)
        page = self.client.get(reverse("question_edit", args=[self.q.pk]))
        self.assertContains(page, "artık değiştirilemez")
        self.client.post(reverse("question_edit", args=[self.q.pk]), self.edit_data())
        self.q.refresh_from_db()
        self.assertEqual(self.q.title, old_title)
        self.assertEqual(self.q.closes_at, old_closes)
        self.assertEqual(self.q.resolution_criteria, "Resmi skor")
        self.assertEqual([x.text for x in self.q.choices.all()], old_choices)
        # açıklama ve kategori serbest
        self.assertEqual(self.q.description, "Yeni açıklama")
        self.assertEqual(self.q.category, "teknoloji")

    def test_service_refuses_core_change_after_prediction_even_if_called_directly(self):
        Prediction.objects.create(question=self.q, choice=self.q.choices.first(), user=make_user("ali"))
        data = {"title": "Hile", "description": "", "resolution_criteria": "Hile", "category": "diger",
                "closes_at": timezone.now() + timedelta(days=9), "choices": ["1", "2"]}
        services.update_question(self.owner, self.q.pk, data)
        self.q.refresh_from_db()
        self.assertEqual(self.q.title, "Maç kim kazanır?")
        self.assertEqual(self.q.choices.count(), 2)
        self.assertEqual(self.q.choices.first().text, "A takımı")

    def test_non_owner_cannot_edit_or_delete(self):
        self.client.force_login(self.other)
        for name in ("question_edit", "question_delete", "question_resolve", "question_cancel"):
            self.assertEqual(self.client.get(reverse(name, args=[self.q.pk])).status_code, 404, name)
            self.assertEqual(self.client.post(reverse(name, args=[self.q.pk]), {}).status_code, 404, name)
        self.assertTrue(Question.objects.filter(pk=self.q.pk).exists())

    def test_guest_cannot_manage(self):
        for name in ("question_edit", "question_delete", "question_resolve", "question_cancel"):
            r = self.client.post(reverse(name, args=[self.q.pk]), {})
            self.assertEqual(r.status_code, 302)
            self.assertIn("/giris/", r["Location"])

    def test_delete_without_predictions(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("question_delete", args=[self.q.pk])), "emin misin")
        r = self.client.post(reverse("question_delete", args=[self.q.pk]))
        self.assertRedirects(r, "/sorularim/")
        self.assertFalse(Question.objects.exists())

    def test_cannot_delete_after_first_prediction(self):
        Prediction.objects.create(question=self.q, choice=self.q.choices.first(), user=make_user("ali"))
        self.client.force_login(self.owner)
        r = self.client.post(reverse("question_delete", args=[self.q.pk]), follow=True)
        self.assertContains(r, "Tahmin almış bir soru silinemez.")
        self.assertTrue(Question.objects.filter(pk=self.q.pk).exists())
        with self.assertRaises(services.ServiceError):
            services.delete_question(self.owner, self.q.pk)

    def test_cannot_edit_resolved_question(self):
        close(self.q)
        services.resolve_question(self.owner, self.q.pk, self.q.choices.first().pk, "Sonuç açıklandı")
        self.client.force_login(self.owner)
        r = self.client.post(reverse("question_edit", args=[self.q.pk]), self.edit_data(), follow=True)
        self.assertContains(r, "Sonuçlanan ya da iptal edilen soru düzenlenemez.")
        self.q.refresh_from_db()
        self.assertEqual(self.q.title, "Maç kim kazanır?")


# ============================================================================ sonuç ve puan
class ResolutionTests(TestCase):
    def setUp(self):
        self.owner = make_user("sahip")
        self.winner1, self.winner2, self.loser = make_user("w1"), make_user("w2"), make_user("l1")
        self.q = make_question(self.owner, choices=("A", "B"))
        self.a, self.b = self.q.choices.all()
        for user, choice in [(self.winner1, self.a), (self.winner2, self.a), (self.loser, self.b)]:
            Prediction.objects.create(question=self.q, choice=choice, user=user)

    def resolve(self, choice=None, note="Resmi sonuç açıklandı", url=""):
        return services.resolve_question(self.owner, self.q.pk, (choice or self.a).pk, note, url)

    def test_cannot_resolve_before_close(self):
        with self.assertRaisesMessage(services.ServiceError, "tahmin süresi dolduktan sonra"):
            self.resolve()
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.OPEN)
        self.assertEqual(Prediction.objects.filter(points_awarded__gt=0).count(), 0)

    def test_correct_predictors_get_10_points_losers_zero(self):
        close(self.q)
        self.assertEqual(self.resolve(), 2)
        pts = {p.user.username: (p.is_correct, p.points_awarded) for p in Prediction.objects.all()}
        self.assertEqual(pts, {"w1": (True, 10), "w2": (True, 10), "l1": (False, 0)})
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.RESOLVED)
        self.assertEqual(self.q.correct_choice, self.a)
        self.assertIsNotNone(self.q.resolved_at)

    def test_points_are_given_only_once_even_if_resolved_again(self):
        close(self.q)
        self.resolve()
        for choice in (self.a, self.b):
            with self.assertRaises(services.ServiceError):
                self.resolve(choice=choice)
        self.assertEqual(sum(p.points_awarded for p in Prediction.objects.all()), 20)
        self.q.refresh_from_db()
        self.assertEqual(self.q.correct_choice, self.a)  # sonuç sonradan değişmedi

    def test_result_cannot_be_changed_via_view_either(self):
        close(self.q)
        self.resolve()
        self.client.force_login(self.owner)
        r = self.client.post(reverse("question_resolve", args=[self.q.pk]),
                             {"choice": self.b.pk, "note": "Fikrimi değiştirdim", "confirm": "1"}, follow=True)
        self.assertContains(r, "Sonuç yalnızca tahmin süresi dolduktan sonra, bir kez bildirilebilir.")
        self.q.refresh_from_db()
        self.assertEqual(self.q.correct_choice, self.a)
        self.assertEqual(sum(p.points_awarded for p in Prediction.objects.all()), 20)

    def test_only_owner_can_resolve(self):
        close(self.q)
        with self.assertRaises(services.ServiceError):
            services.resolve_question(self.winner1, self.q.pk, self.a.pk, "Ben bildiriyorum")
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.OPEN)

    def test_choice_must_belong_to_question(self):
        close(self.q)
        foreign = make_question(self.owner, title="Başka").choices.first()
        with self.assertRaises(services.ServiceError):
            self.resolve(choice=foreign)
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.OPEN)

    def test_note_required(self):
        close(self.q)
        with self.assertRaisesMessage(services.ServiceError, "kısa bir açıklama"):
            self.resolve(note="  ")
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.OPEN)

    def test_two_step_confirmation_in_view(self):
        close(self.q)
        self.client.force_login(self.owner)
        url = reverse("question_resolve", args=[self.q.pk])
        r = self.client.post(url, {"choice": self.a.pk, "note": "Resmi sonuç buydu", "source_url": "https://example.com/haber"})
        self.assertContains(r, "Bu işlem geri alınamaz")
        self.assertContains(r, "2 kişi 10 puan kazanacak")
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.OPEN)            # onaylanmadan hiçbir şey değişmez
        self.assertEqual(Prediction.objects.filter(points_awarded__gt=0).count(), 0)
        r = self.client.post(url, {"choice": self.a.pk, "note": "Resmi sonuç buydu", "source_url": "https://example.com/haber", "confirm": "1"}, follow=True)
        self.assertContains(r, "2 kişi 10 puan kazandı")
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.RESOLVED)
        self.assertEqual(self.q.resolution_source_url, "https://example.com/haber")

    def test_resolved_page_shows_reported_by_creator_note_and_source(self):
        close(self.q)
        self.resolve(url="https://example.com/haber")
        r = self.client.get(reverse("question_detail", args=[self.q.pk]))
        self.assertContains(r, "Sonuç, soruyu oluşturan kişi tarafından bildirildi")
        self.assertContains(r, "Resmi sonuç açıklandı")
        self.assertContains(r, "https://example.com/haber")
        self.assertContains(r, "Doğru cevap")

    def test_winner_and_loser_see_their_outcome(self):
        close(self.q)
        self.resolve()
        self.client.force_login(self.winner1)
        self.assertContains(self.client.get(reverse("question_detail", args=[self.q.pk])), "Doğru bildin! +10 puan")
        self.client.force_login(self.loser)
        self.assertContains(self.client.get(reverse("question_detail", args=[self.q.pk])), "Bu sefer tutmadı")

    def test_invalid_source_url_rejected(self):
        close(self.q)
        self.client.force_login(self.owner)
        r = self.client.post(reverse("question_resolve", args=[self.q.pk]),
                             {"choice": self.a.pk, "note": "Resmi sonuç buydu", "source_url": "javascript:alert(1)"})
        self.assertContains(r, "Geçerli bir bağlantı gir")
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.OPEN)

    def test_owner_never_earns_points_from_own_question(self):
        # Servis katmanı sahibin tahminini engeller; yine de elle eklenmiş bir kayıt puan almaz.
        force_prediction(question=self.q, choice=self.a, user=self.owner)
        close(self.q)
        self.resolve()
        self.assertEqual(Prediction.objects.get(user=self.owner).points_awarded, 0)

    def test_users_cannot_change_points_or_others_predictions_via_http(self):
        close(self.q)
        self.resolve()
        self.client.force_login(self.loser)
        before = list(Prediction.objects.values_list("pk", "choice_id", "points_awarded"))
        for url in (reverse("predict", args=[self.q.pk]),):
            self.client.post(url, {"choice": self.a.pk, "points_awarded": 999, "user": self.winner1.pk})
        self.assertEqual(before, list(Prediction.objects.values_list("pk", "choice_id", "points_awarded")))


class CancelTests(TestCase):
    def setUp(self):
        self.owner, self.u = make_user("sahip"), make_user("ali")
        self.q = make_question(self.owner)
        Prediction.objects.create(question=self.q, choice=self.q.choices.first(), user=self.u)

    def test_cancel_with_reason_gives_no_points(self):
        close(self.q)
        services.cancel_question(self.owner, self.q.pk, "Resmi sonuç hiç açıklanmadı")
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.CANCELLED)
        self.assertEqual(Prediction.objects.get().points_awarded, 0)
        self.assertIsNone(Prediction.objects.get().is_correct)

    def test_reason_required(self):
        with self.assertRaisesMessage(services.ServiceError, "gerekçe"):
            services.cancel_question(self.owner, self.q.pk, "kısa")
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.OPEN)

    def test_cannot_resolve_after_cancel_nor_cancel_twice_nor_cancel_resolved(self):
        close(self.q)
        services.cancel_question(self.owner, self.q.pk, "Resmi sonuç hiç açıklanmadı")
        with self.assertRaises(services.ServiceError):
            services.resolve_question(self.owner, self.q.pk, self.q.choices.first().pk, "Şimdi çözüldü")
        with self.assertRaises(services.ServiceError):
            services.cancel_question(self.owner, self.q.pk, "Tekrar iptal etmeye çalışıyorum")
        other = close(make_question(self.owner, title="Başka"))
        services.resolve_question(self.owner, other.pk, other.choices.first().pk, "Sonuç açıklandı")
        with self.assertRaises(services.ServiceError):
            services.cancel_question(self.owner, other.pk, "Sonradan iptal edilemez")

    def test_cancel_view_two_step_and_page(self):
        self.client.force_login(self.owner)
        url = reverse("question_cancel", args=[self.q.pk])
        r = self.client.post(url, {"reason": "Sonuç belirlenemedi, kaynak yok"})
        self.assertContains(r, "Bu işlem geri alınamaz")
        self.q.refresh_from_db()
        self.assertEqual(self.q.status, Status.OPEN)
        r = self.client.post(url, {"reason": "Sonuç belirlenemedi, kaynak yok", "confirm": "1"}, follow=True)
        self.assertContains(r, "Soru iptal edildi")
        self.assertContains(r, "Sonuç belirlenemedi, kaynak yok")
        self.assertContains(r, "Kimseye puan verilmedi")


# ============================================================================ sayfalar
class PagesTests(TestCase):
    def setUp(self):
        self.owner = make_user("sahip", email="gizli.sahip@example.com")
        self.u = make_user("ali", email="gizli.ali@example.com")
        self.open_q = make_question(self.owner, title="Açık soru", category="spor")
        self.open_tech = make_question(self.owner, title="Teknoloji sorusu", category="teknoloji")
        self.pending = close(make_question(self.owner, title="Bekleyen soru"))
        self.done = close(make_question(self.owner, title="Biten soru"))
        force_prediction(question=self.done, choice=self.done.choices.first(), user=self.u)
        services.resolve_question(self.owner, self.done.pk, self.done.choices.first().pk, "Sonuç açıklandı")

    def titles(self, url):
        return [q.title for q in self.client.get(url).context["page"]]

    def test_home_tabs(self):
        self.assertEqual(set(self.titles("/")), {"Açık soru", "Teknoloji sorusu"})
        self.assertEqual(self.titles("/?sekme=bekleyen"), ["Bekleyen soru"])
        self.assertEqual(self.titles("/?sekme=sonuclanan"), ["Biten soru"])
        self.assertEqual(set(self.titles("/?sekme=saçma")), {"Açık soru", "Teknoloji sorusu"})

    def test_home_category_filter(self):
        self.assertEqual(self.titles("/?kategori=spor"), ["Açık soru"])
        self.assertEqual(self.titles("/?kategori=teknoloji"), ["Teknoloji sorusu"])
        self.assertEqual(len(self.titles("/?kategori=yok")), 2)
        self.assertEqual(self.titles("/?kategori=eglence"), [])

    def test_home_shows_category_status_and_remaining_time(self):
        r = self.client.get("/")
        self.assertContains(r, "Spor")
        self.assertContains(r, "Tahmine açık")
        self.assertContains(r, "data-countdown")
        self.assertContains(self.client.get("/?sekme=bekleyen"), "Sonuç bekliyor")

    def test_home_empty_state(self):
        Question.objects.all().delete()
        self.assertContains(self.client.get("/"), "tahmine açık soru yok")
        self.assertContains(self.client.get("/?sekme=sonuclanan"), "Henüz sonuçlanan soru yok")

    def test_my_predictions_shows_choice_and_points(self):
        self.client.force_login(self.u)
        r = self.client.get("/tahminlerim/")
        self.assertContains(r, "Biten soru")
        self.assertContains(r, "+10 puan")
        self.assertEqual(r.context["total_points"], 10)
        self.assertRedirects(self.client.__class__().get("/tahminlerim/"), "/giris/?next=/tahminlerim/")

    def test_my_questions_lists_only_own_and_actions(self):
        make_question(self.u, title="Alinin sorusu")
        self.client.force_login(self.owner)
        r = self.client.get("/sorularim/")
        self.assertContains(r, "Açık soru")
        self.assertNotContains(r, "Alinin sorusu")
        self.assertContains(r, "Sonucu Bildir")       # bekleyen soru için
        self.assertContains(r, "Düzenle")
        self.assertRedirects(Client().get("/sorularim/"), "/giris/?next=/sorularim/")

    def test_leaderboard_ranking_ties_and_privacy(self):
        c = close(make_question(self.owner, title="İkinci"))
        for name, pick in (("ali", 0), ("veli", 0), ("can", 1)):
            force_prediction(question=c, choice=c.choices.all()[pick], user=User.objects.get_or_create(
                username=name, defaults={"email": f"{name}@example.com"})[0])
        services.resolve_question(self.owner, c.pk, c.choices.first().pk, "Sonuç açıklandı")
        rows = self.client.get("/puan-tablosu/").context["rows"]
        self.assertEqual([(r["username"], r["total_points"], r["rank"]) for r in rows],
                         [("ali", 20, 1), ("veli", 10, 2), ("can", 0, 3)])
        self.assertEqual(rows[0]["correct_count"], 2)

    def test_leaderboard_is_public_and_hides_email(self):
        r = self.client.get("/puan-tablosu/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "@ali")
        self.assertNotContains(r, "example.com")
        self.assertTrue(all(set(row) == {"username", "total_points", "correct_count", "judged_count", "rank", "is_me"}
                            for row in r.context["rows"]))

    def test_leaderboard_empty_state(self):
        Prediction.objects.all().delete()
        self.assertContains(self.client.get("/puan-tablosu/"), "henüz boş")

    def test_email_never_on_public_pages(self):
        for url in ["/", "/?sekme=sonuclanan", f"/soru/{self.done.pk}/", f"/soru/{self.open_q.pk}/", "/puan-tablosu/",
                    "/giris/", "/kayit/"]:
            self.assertNotContains(self.client.get(url), "example.com", msg_prefix=url)
        self.client.force_login(self.u)
        for url in ["/", f"/soru/{self.done.pk}/", "/tahminlerim/", "/sorularim/", "/puan-tablosu/"]:
            html = self.client.get(url).content.decode()
            self.assertNotIn("gizli.", html, url)

    def test_guests_can_see_questions_distribution_results_and_board(self):
        for url in ["/", f"/soru/{self.open_q.pk}/", f"/soru/{self.done.pk}/", "/puan-tablosu/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get(f"/soru/{self.done.pk}/"), "Doğru cevap")
        self.assertContains(self.client.get(f"/soru/{self.open_q.pk}/"), "Tahmin yapmak için giriş yap")

    def test_times_rendered_for_local_conversion(self):
        r = self.client.get(f"/soru/{self.open_q.pk}/")
        self.assertContains(r, "data-local")
        self.assertRegex(r.content.decode(), r'datetime="\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"')

    def test_pending_page_tells_creator_will_announce(self):
        self.assertContains(self.client.get(f"/soru/{self.pending.pk}/"), "Sonucu soruyu oluşturan kişi açıklayacak")


class BrandingTests(TestCase):
    def test_name_slogan_metadata_and_no_old_name(self):
        make_user("ali")
        q = make_question(User.objects.get(username="ali"))
        for url in ["/", f"/soru/{q.pk}/", "/puan-tablosu/", "/giris/", "/kayit/", "/yok-boyle-sayfa/"]:
            r = self.client.get(url)
            html = r.content.decode()
            self.assertIn("Tahmince", html, url)
            self.assertNotIn("Kararsızım", html, url)
            self.assertIn('property="og:site_name" content="Tahmince"', html, url)
        self.assertContains(self.client.get("/"), "Tahminini yap,")
        self.assertContains(self.client.get("/"), "sonucu gör!")
        self.assertContains(self.client.get("/"), "<title>Tahmince · Tahminini yap, sonucu gör!</title>", html=True)

    def test_concept_wording_and_no_money_features(self):
        html = self.client.get("/").content.decode()
        self.assertIn("Tahmin Sorusu Oluştur", html)
        self.assertNotIn("Anket Oluştur", html)
        self.assertIn("para, bahis, ödeme veya ödül yoktur", html)
        for word in ("bahis oyna", "ödeme yap", "bakiye", "kupon"):
            self.assertNotIn(word, html.lower())


class RemovedLegacyPollsTests(TestCase):
    """Eski "Kararsızım" anketleri tamamen kaldırıldı: sayfalar ve eski adresler artık yok."""

    def test_old_pages_and_urls_are_gone(self):
        for url in ["/eski-anketler/", "/eski-anketler/1/", "/anket/1/", "/anket/yeni/", "/anketlerim/", "/populer/", "/anket/1/oy/"]:
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_navbar_has_no_old_polls_link(self):
        self.assertNotContains(self.client.get("/"), "Eski Anketler")
        self.assertNotContains(self.client.get("/"), "eski-anketler")

    def test_no_legacy_voter_cookie(self):
        self.assertNotIn("voter_id", self.client.get("/").cookies)


# ============================================================================ inceleme düzeltmeleri
class DailyQuestionLimitTests(TestCase):
    """#2: aynı hesap 24 saatte en fazla MAX_QUESTIONS_PER_DAY soru açabilir."""

    def setUp(self):
        self.user = make_user("ayse")
        self.future = (timezone.localtime() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")

    def data(self, n):
        return {"title": f"Soru {n}", "resolution_criteria": "x", "category": "diger", "closes_at": self.future,
                "choice_1": "A", "choice_2": "B"}

    def test_limit_enforced_and_message_shown(self):
        self.client.force_login(self.user)
        for n in range(services.MAX_QUESTIONS_PER_DAY):
            self.client.post("/soru/yeni/", self.data(n))
        self.assertEqual(Question.objects.filter(created_by=self.user).count(), services.MAX_QUESTIONS_PER_DAY)
        r = self.client.post("/soru/yeni/", self.data(99))
        self.assertContains(r, "Günde en fazla")
        self.assertEqual(Question.objects.filter(created_by=self.user).count(), services.MAX_QUESTIONS_PER_DAY)

    def test_limit_is_per_user_and_expires_after_a_day(self):
        for n in range(services.MAX_QUESTIONS_PER_DAY):
            make_question(self.user, title=f"S{n}")
        other = make_user("veli")
        self.client.force_login(other)
        self.assertEqual(self.client.post("/soru/yeni/", self.data(1)).status_code, 302)  # başkası etkilenmez
        Question.objects.filter(created_by=self.user).update(created_at=timezone.now() - timedelta(days=2),
                                                             closes_at=timezone.now() + timedelta(days=1))
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/soru/yeni/", self.data(2)).status_code, 302)  # 24 saat geçince yeniden açılır


class SourceWarningTests(TestCase):
    """#3: kaynak yoksa sonucun yalnızca beyana dayandığı açıkça yazılır; kaynak varsa uyarı yok."""

    def resolved(self, url):
        owner = make_user("sahip" + ("1" if url else "0"))
        q = close(make_question(owner, title="K" + ("1" if url else "0")))
        services.resolve_question(owner, q.pk, q.choices.first().pk, "Sonuç açıklandı", url)
        return q

    def test_warning_only_without_source(self):
        no_src, with_src = self.resolved(""), self.resolved("https://example.com/haber")
        self.assertContains(self.client.get(f"/soru/{no_src.pk}/"), "Kaynak bağlantısı belirtilmedi")
        r = self.client.get(f"/soru/{with_src.pk}/")
        self.assertNotContains(r, "Kaynak bağlantısı belirtilmedi")
        self.assertContains(r, "https://example.com/haber")

    def test_source_stays_optional(self):
        owner = make_user("sahip")
        q = close(make_question(owner))
        c = Client(); c.force_login(owner)
        r = c.post(f"/soru/{q.pk}/sonuc/", {"choice": q.choices.first().pk, "note": "Resmi sonuç buydu", "confirm": "1"}, follow=True)
        self.assertContains(r, "Sonuç açıklandı")


class AccountDeletionProtectionTests(TestCase):
    """#4: hesap silme, başkalarının tahminlerini ve puanlarını silmemeli."""

    def test_deleting_question_owner_or_predictor_is_blocked_and_nothing_is_lost(self):
        from django.db.models import ProtectedError
        owner, winner = make_user("sahip"), make_user("kazanan")
        q = make_question(owner)
        force_prediction(question=q, choice=q.choices.first(), user=winner)
        close(q)
        services.resolve_question(owner, q.pk, q.choices.first().pk, "Sonuç açıklandı")
        for user in (owner, winner):
            with self.assertRaises(ProtectedError):
                user.delete()
        self.assertEqual(Prediction.objects.get().points_awarded, 10)
        self.assertTrue(Question.objects.filter(pk=q.pk).exists())

    def test_user_without_activity_can_still_be_deleted(self):
        make_user("bos").delete()
        self.assertFalse(User.objects.filter(username="bos").exists())


class AdminModerationTests(TestCase):
    """#5: yönetici soruları görüp silebilir, düzenleyemez/ekleyemez."""

    def setUp(self):
        self.admin = User.objects.create_superuser(username="yonetici", email="yonetici@example.com", password=PASSWORD)
        self.owner, self.u = make_user("sahip"), make_user("ali")
        self.q = make_question(self.owner)
        Prediction.objects.create(question=self.q, choice=self.q.choices.first(), user=self.u)
        self.client.force_login(self.admin)

    def test_registered_and_pages_render(self):
        for url in ["/admin/predictions/question/", f"/admin/predictions/question/{self.q.pk}/change/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get("/admin/predictions/question/"), self.q.title)

    def test_no_add_and_no_edit(self):
        self.assertEqual(self.client.get("/admin/predictions/question/add/").status_code, 403)
        r = self.client.post(f"/admin/predictions/question/{self.q.pk}/change/", {"title": "Hile"})
        self.q.refresh_from_db()
        self.assertEqual(self.q.title, "Maç kim kazanır?")
        self.assertIn(r.status_code, (302, 403))

    def test_admin_can_delete_abusive_question_and_regular_users_cannot_reach_admin(self):
        r = self.client.post(f"/admin/predictions/question/{self.q.pk}/delete/", {"post": "yes"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Question.objects.filter(pk=self.q.pk).exists())
        self.client.force_login(self.u)
        self.assertEqual(self.client.get("/admin/predictions/question/").status_code, 302)  # girişe yönlenir

    def test_predictions_shown_read_only_on_question_page_and_not_deletable_individually(self):
        r = self.client.get(f"/admin/predictions/question/{self.q.pk}/change/")
        self.assertContains(r, "ali")                       # tahmin sahibi görünür
        self.assertEqual(self.client.get("/admin/predictions/prediction/").status_code, 404)  # ayrı yönetim sayfası yok
        self.assertEqual(Prediction.objects.count(), 1)


class ServerTimeTests(TestCase):
    """#1: sayfa, cihaz saati yanlış olsa da düzeltme yapabilsin diye sunucu saatini taşır."""

    def test_body_carries_server_time_in_epoch_seconds(self):
        import re, time
        html = self.client.get("/").content.decode()
        m = re.search(r'<body data-server-time="(\d{10})"', html)
        self.assertIsNotNone(m)
        self.assertLess(abs(int(m.group(1)) - time.time()), 5)

    def test_open_question_marks_reload_time_in_utc(self):
        q = make_question(make_user("sahip"))
        self.assertRegex(self.client.get(f"/soru/{q.pk}/").content.decode(), r'data-reload-at="\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"')
