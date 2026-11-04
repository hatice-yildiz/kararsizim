"""Eski anketler artık salt okunur arşivdir; veriler korunur, oylama/oluşturma/silme yoktur."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Option, Poll, Vote

User = get_user_model()


def make_poll(user, question="Çay mı kahve mi?", options=("Çay", "Kahve")):
    poll = Poll.objects.create(question=question, created_by=user)
    for i, text in enumerate(options, start=1):
        Option.objects.create(poll=poll, text=text, order=i)
    return poll


class LegacyArchiveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="eski", email="eski@example.com", password="p")
        self.poll = make_poll(self.user)
        a, b = self.poll.options.all()
        for i, opt in enumerate([a, a, b]):
            Vote.objects.create(poll=self.poll, option=opt, voter_key=f"a:{i}")

    def test_list_and_detail_are_public_and_read_only(self):
        r = self.client.get("/eski-anketler/")
        self.assertContains(r, "Çay mı kahve mi?")
        self.assertContains(r, "3 oy")
        r = self.client.get(f"/eski-anketler/{self.poll.pk}/")
        self.assertContains(r, "Oylama kapalıdır")
        self.assertContains(r, "%67")
        self.assertNotContains(r, 'name="option"')
        self.assertNotContains(r, "<form")

    def test_voting_creating_and_deleting_routes_are_gone(self):
        before = Vote.objects.count()
        for url in (f"/anket/{self.poll.pk}/oy/", f"/anket/{self.poll.pk}/sil/"):
            self.assertEqual(self.client.post(url, {"option": 1}).status_code, 404)
        self.assertEqual(Vote.objects.count(), before)
        self.assertEqual(Poll.objects.count(), 1)

    def test_no_anonymous_voter_cookie_is_issued_any_more(self):
        self.assertNotIn("voter_id", self.client.get("/").cookies)

    def test_old_data_untouched(self):
        self.assertEqual((Poll.objects.count(), Option.objects.count(), Vote.objects.count()), (1, 2, 3))

    def test_old_votes_never_create_points(self):
        from predictions.models import Prediction
        self.assertEqual(Prediction.objects.count(), 0)
        self.assertEqual(self.client.get("/puan-tablosu/").context["rows"], [])

    def test_missing_poll_404(self):
        self.assertEqual(self.client.get("/eski-anketler/9999/").status_code, 404)
