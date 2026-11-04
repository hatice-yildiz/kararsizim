"""Veritabanı tetikleyicileri (migrations/0002_db_guards.py) — yalnızca PostgreSQL'de çalışır.

Çalıştırmak için PostgreSQL'e bağlan:  DATABASE_URL=postgresql://... python manage.py test predictions.tests_postgres
Burada servis katmanı kasıtlı olarak atlanır; kurallar doğrudan ORM/SQL ile çiğnenmeye çalışılır.
"""
from datetime import timedelta
from unittest import skipUnless

from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from .models import Choice, Prediction, Question
from .tests import close, force_prediction, make_question, make_user


@skipUnless(connection.vendor == "postgresql", "Tetikleyiciler yalnızca PostgreSQL'de vardır")
class DatabaseGuardTests(TestCase):
    def setUp(self):
        self.owner, self.u, self.v = make_user("sahip"), make_user("ali"), make_user("veli")
        self.q = make_question(self.owner, choices=("A", "B", "C"))
        self.a, self.b, self.c = self.q.choices.all()

    def blocked(self, fn):
        """fn()'in veritabanı tarafından reddedildiğini doğrular (işlemi savepoint ile korur)."""
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                fn()

    # ---- tahmin kuralları
    def test_prediction_after_close_rejected(self):
        close(self.q)
        self.blocked(lambda: Prediction.objects.create(question=self.q, choice=self.a, user=self.u))
        self.assertEqual(Prediction.objects.count(), 0)

    def test_changing_prediction_after_close_rejected(self):
        p = Prediction.objects.create(question=self.q, choice=self.a, user=self.u)
        close(self.q)
        p.choice = self.b
        self.blocked(lambda: p.save(update_fields=["choice"]))
        p.refresh_from_db()
        self.assertEqual(p.choice, self.a)

    def test_changing_prediction_before_close_allowed(self):
        p = Prediction.objects.create(question=self.q, choice=self.a, user=self.u)
        p.choice = self.b
        p.save(update_fields=["choice"])
        p.refresh_from_db()
        self.assertEqual(p.choice, self.b)

    def test_owner_cannot_predict_own_question(self):
        self.blocked(lambda: Prediction.objects.create(question=self.q, choice=self.a, user=self.owner))

    def test_choice_must_belong_to_question(self):
        foreign = make_question(self.owner, title="Başka").choices.first()
        self.blocked(lambda: Prediction.objects.create(question=self.q, choice=foreign, user=self.u))

    def test_one_prediction_per_user_per_question(self):
        Prediction.objects.create(question=self.q, choice=self.a, user=self.u)
        self.blocked(lambda: Prediction.objects.create(question=self.q, choice=self.b, user=self.u))

    def test_prediction_owner_and_question_immutable(self):
        p = Prediction.objects.create(question=self.q, choice=self.a, user=self.u)
        other = make_question(self.owner, title="Diğer")
        self.blocked(lambda: Prediction.objects.filter(pk=p.pk).update(user=self.v))
        self.blocked(lambda: Prediction.objects.filter(pk=p.pk).update(question=other, choice=other.choices.first()))

    def test_points_cannot_be_inserted_or_set_by_hand(self):
        self.blocked(lambda: Prediction.objects.create(question=self.q, choice=self.a, user=self.u, is_correct=True, points_awarded=10))
        p = Prediction.objects.create(question=self.q, choice=self.a, user=self.u)
        self.blocked(lambda: Prediction.objects.filter(pk=p.pk).update(is_correct=True, points_awarded=10))  # soru çözülmedi

    # ---- soru kuralları
    def test_title_closing_and_criteria_locked_after_first_prediction(self):
        Prediction.objects.create(question=self.q, choice=self.a, user=self.u)
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(title="Hile"))
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(closes_at=timezone.now() + timedelta(days=30)))
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(resolution_criteria="Hile"))
        Question.objects.filter(pk=self.q.pk).update(description="Serbest")  # açıklama değişebilir
        Question.objects.filter(pk=self.q.pk).update(category="diger")

    def test_title_editable_before_first_prediction(self):
        Question.objects.filter(pk=self.q.pk).update(title="Yeni")
        self.q.refresh_from_db()
        self.assertEqual(self.q.title, "Yeni")

    def test_closing_must_stay_in_future_when_edited(self):
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(closes_at=timezone.now() - timedelta(minutes=5)))

    def test_cannot_resolve_before_close_or_with_foreign_choice(self):
        foreign = make_question(self.owner, title="Başka").choices.first()
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(
            status="resolved", correct_choice=self.a, resolved_at=timezone.now()))      # kapanmadı
        close(self.q)
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(
            status="resolved", correct_choice=foreign, resolved_at=timezone.now()))     # yabancı seçenek

    def test_resolved_question_is_immutable(self):
        close(self.q)
        Question.objects.filter(pk=self.q.pk).update(status="resolved", correct_choice=self.a, resolved_at=timezone.now())
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(correct_choice=self.b))
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(status="cancelled", cancel_reason="x" * 12))
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(description="değişti"))

    def test_cancelled_question_is_immutable(self):
        Question.objects.filter(pk=self.q.pk).update(status="cancelled", cancel_reason="Gerekçe yeterince uzun", resolved_at=timezone.now())
        self.blocked(lambda: Question.objects.filter(pk=self.q.pk).update(status="open", cancel_reason=""))

    def test_question_with_predictions_cannot_be_deleted_with_raw_sql(self):
        # Not: Django ORM silmeyi çocuklardan başlatır (önce tahminler); bu koruma doğrudan SQL DELETE içindir.
        # Uygulamadaki silme yolu services.delete_question tahmin varlığını ayrıca denetler.
        Prediction.objects.create(question=self.q, choice=self.a, user=self.u)

        def raw_delete():
            with connection.cursor() as cur:
                cur.execute("DELETE FROM predictions_question WHERE id = %s", [self.q.pk])

        self.blocked(raw_delete)
        self.assertTrue(Question.objects.filter(pk=self.q.pk).exists())

    def test_question_without_predictions_can_be_deleted_even_if_resolved(self):
        close(self.q)
        Question.objects.filter(pk=self.q.pk).update(status="resolved", correct_choice=self.a, resolved_at=timezone.now())
        self.q.delete()
        self.assertFalse(Question.objects.exists())
        self.assertFalse(Choice.objects.exists())

    # ---- seçenek kuralları
    def test_choices_locked_after_first_prediction(self):
        Prediction.objects.create(question=self.q, choice=self.a, user=self.u)
        self.blocked(lambda: Choice.objects.filter(pk=self.b.pk).update(text="Hile"))
        self.blocked(lambda: Choice.objects.filter(pk=self.b.pk).delete())
        self.blocked(lambda: Choice.objects.create(question=self.q, text="Yeni", position=9))

    def test_choices_editable_before_first_prediction(self):
        Choice.objects.filter(pk=self.b.pk).update(text="Düzenlendi")
        self.b.refresh_from_db()
        self.assertEqual(self.b.text, "Düzenlendi")

    # ---- puan dağıtımı
    def _resolve_with_predictions(self):
        force_prediction(question=self.q, choice=self.a, user=self.u)
        force_prediction(question=self.q, choice=self.b, user=self.v)
        close(self.q)
        Question.objects.filter(pk=self.q.pk).update(status="resolved", correct_choice=self.a, resolved_at=timezone.now())

    def test_points_only_for_correct_choice_amount_10_and_only_once(self):
        self._resolve_with_predictions()
        win = Prediction.objects.get(user=self.u)
        lose = Prediction.objects.get(user=self.v)
        self.blocked(lambda: Prediction.objects.filter(pk=win.pk).update(is_correct=True, points_awarded=50))    # miktar hatalı
        self.blocked(lambda: Prediction.objects.filter(pk=lose.pk).update(is_correct=True, points_awarded=10))   # yanlış seçeneğe puan
        self.blocked(lambda: Prediction.objects.filter(pk=win.pk).update(is_correct=False, points_awarded=0))    # doğruya 0 yazma
        Prediction.objects.filter(pk=win.pk).update(is_correct=True, points_awarded=10)
        Prediction.objects.filter(pk=lose.pk).update(is_correct=False)
        # ikinci dağıtım ya da sonradan değiştirme
        self.blocked(lambda: Prediction.objects.filter(pk=win.pk).update(points_awarded=20))
        self.blocked(lambda: Prediction.objects.filter(pk=win.pk).update(is_correct=False, points_awarded=0))
        self.blocked(lambda: Prediction.objects.filter(pk=lose.pk).update(is_correct=True, points_awarded=10))
        win.refresh_from_db()
        self.assertEqual(win.points_awarded, 10)

    def test_no_points_on_cancelled_question(self):
        force_prediction(question=self.q, choice=self.a, user=self.u)
        Question.objects.filter(pk=self.q.pk).update(status="cancelled", cancel_reason="Gerekçe yeterince uzun", resolved_at=timezone.now())
        self.blocked(lambda: Prediction.objects.filter(user=self.u).update(is_correct=True, points_awarded=10))

    def test_owner_cannot_earn_points(self):
        force_prediction(question=self.q, choice=self.a, user=self.owner)
        close(self.q)
        Question.objects.filter(pk=self.q.pk).update(status="resolved", correct_choice=self.a, resolved_at=timezone.now())
        self.blocked(lambda: Prediction.objects.filter(user=self.owner).update(is_correct=True, points_awarded=10))

    def test_rls_enabled_on_all_tables(self):
        with connection.cursor() as cur:
            cur.execute("select tablename from pg_tables where schemaname='public' and not rowsecurity")
            self.assertEqual(cur.fetchall(), [])


@skipUnless(connection.vendor == "postgresql", "Tetikleyiciler yalnızca PostgreSQL'de vardır")
class TriggerErrorMappingTests(TestCase):
    """Tetikleyici hataları kullanıcıya anlaşılır mesajla dönmeli (500 sayfası değil)."""

    def test_trigger_errors_carry_sqlstate_P0001_that_services_recognise(self):
        # Django bunu ProgrammingError olarak verir (IntegrityError değil); services._db_rules SQLSTATE P0001'e bakar.
        owner, u = make_user("sahip"), make_user("ali")
        q = close(make_question(owner))
        with self.assertRaises(DatabaseError) as ctx:
            with transaction.atomic():
                Prediction.objects.create(question=q, choice=q.choices.first(), user=u)
        self.assertEqual(getattr(ctx.exception.__cause__, "sqlstate", None), "P0001")

    def test_service_turns_database_rejection_into_friendly_message(self):
        # Servis kontrolü ile yazma arasında kapanış olursa (yarış), veritabanı reddeder; kullanıcı Türkçe mesaj görmeli.
        from unittest import mock
        from . import services
        owner, u = make_user("sahip"), make_user("ali")
        q = make_question(owner)
        close(q)
        # Python tarafındaki süre kontrolünü "henüz açık" gösterecek şekilde yanıltıp DB'yi sınıyoruz
        real_now = timezone.now
        with mock.patch("predictions.services.timezone.now", return_value=real_now() - timedelta(days=5)):
            with mock.patch.object(Question, "status", "open", create=True):
                with self.assertRaises(services.ServiceError) as ctx:
                    services.make_prediction(u, q.pk, q.choices.first().pk)
        self.assertIn("veritabanı kurallarına takıldı", str(ctx.exception))
        self.assertEqual(Prediction.objects.count(), 0)


import threading

from django.test import TransactionTestCase


@skipUnless(connection.vendor == "postgresql", "Gerçek eşzamanlılık yalnızca PostgreSQL'de denenir")
class ConcurrentResolutionTests(TransactionTestCase):
    """İki bağlantı aynı anda sonucu bildirmeye çalışınca puan yalnızca bir kez dağıtılmalı."""

    def run_race(self, n_threads):
        from . import services
        owner = make_user("sahip")
        voters = [make_user(f"u{i}") for i in range(4)]
        q = make_question(owner, choices=("A", "B"))
        a, b = q.choices.all()
        for i, v in enumerate(voters):
            force_prediction(question=q, choice=a if i < 3 else b, user=v)   # 3 kişi A, 1 kişi B
        close(q)
        barrier, results = threading.Barrier(n_threads), []

        def worker(choice):
            try:
                barrier.wait(timeout=10)
                services.resolve_question(owner, q.pk, choice.pk, "Eşzamanlı sonuç denemesi")
                results.append("ok")
            except services.ServiceError:
                results.append("reddedildi")
            except Exception as exc:  # beklenmeyen bir hata testi düşürmeli
                results.append(f"HATA: {type(exc).__name__}: {exc}")
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(a if i % 2 == 0 else b,)) for i in range(n_threads)]
        [t.start() for t in threads]
        [t.join(30) for t in threads]
        return q, a, results

    def test_two_simultaneous_resolutions_award_points_exactly_once(self):
        q, a, results = self.run_race(2)
        self.assertEqual(sorted(results), ["ok", "reddedildi"], results)
        q.refresh_from_db()
        self.assertEqual(q.status, "resolved")
        total = sum(Prediction.objects.filter(question=q).values_list("points_awarded", flat=True))
        winners = Prediction.objects.filter(question=q, points_awarded=10).count()
        # Kazanan seçenek A ise 3 kişi, B ise 1 kişi 10 puan alır; asla ikisi birden, asla iki kez.
        self.assertIn((winners, total), [(3, 30), (1, 10)])
        self.assertEqual(Prediction.objects.filter(question=q, is_correct=True).count(), winners)
        self.assertEqual(Prediction.objects.filter(question=q, is_correct__isnull=True).count(), 0)

    def test_many_simultaneous_resolutions_still_exactly_one_winner(self):
        q, a, results = self.run_race(6)
        self.assertEqual(results.count("ok"), 1, results)
        self.assertEqual(results.count("reddedildi"), 5, results)
        self.assertIn(sum(Prediction.objects.filter(question=q).values_list("points_awarded", flat=True)), (30, 10))
