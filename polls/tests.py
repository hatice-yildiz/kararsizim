from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Option, Poll, Vote

User = get_user_model()


def make_poll(user, question="Sinema mı yemek mi?", options=("Sinema", "Yemek")):
    poll = Poll.objects.create(question=question, created_by=user)
    for i, text in enumerate(options, start=1):
        Option.objects.create(poll=poll, text=text, order=i)
    return poll


class PollCreateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ali", email="ali@example.com", password="p")
        self.url = reverse("poll_create")

    def post(self, **options):
        data = {"question": "Ne yapsam?", "description": ""}
        data.update(options)
        return self.client.post(self.url, data)

    def test_guest_redirected_to_login(self):
        r = self.client.get(self.url)
        self.assertRedirects(r, "/giris/?next=/anket/yeni/")

    def test_create_with_two_options(self):
        self.client.force_login(self.user)
        r = self.post(option_1="Sinema", option_2="Yemek")
        poll = Poll.objects.get()
        self.assertRedirects(r, reverse("poll_detail", args=[poll.pk]))
        self.assertEqual(poll.created_by, self.user)
        self.assertEqual([o.text for o in poll.options.all()], ["Sinema", "Yemek"])

    def test_create_with_five_options_and_blank_gaps_ignored(self):
        self.client.force_login(self.user)
        self.post(option_1="A", option_2="", option_3="B", option_4="C", option_5="D")
        self.assertEqual([o.text for o in Poll.objects.get().options.all()], ["A", "B", "C", "D"])
        self.assertEqual([o.order for o in Poll.objects.get().options.all()], [1, 2, 3, 4])

    def test_one_option_rejected(self):
        self.client.force_login(self.user)
        r = self.post(option_1="Sadece bir")
        self.assertContains(r, "En az 2 seçenek girmelisin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_no_options_rejected(self):
        self.client.force_login(self.user)
        self.post(option_1="  ", option_2="")
        self.assertEqual(Poll.objects.count(), 0)

    def test_duplicate_options_rejected_case_and_space_insensitive(self):
        self.client.force_login(self.user)
        r = self.post(option_1="Sinema", option_2="  sinema ", option_3="Yemek")
        self.assertContains(r, "Bu seçenek zaten eklenmiş.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_duplicates_leaving_fewer_than_two_rejected(self):
        self.client.force_login(self.user)
        self.post(option_1="Aynı", option_2="aynı")
        self.assertEqual(Poll.objects.count(), 0)

    def test_more_than_five_options_not_possible(self):
        self.client.force_login(self.user)
        self.post(option_1="A", option_2="B", option_3="C", option_4="D", option_5="E", option_6="F")
        self.assertEqual(Poll.objects.get().options.count(), 5)

    def test_question_required_and_input_preserved(self):
        self.client.force_login(self.user)
        r = self.client.post(self.url, {"question": "", "option_1": "Korunan", "option_2": "B"})
        self.assertContains(r, "Soru zorunludur.")
        self.assertContains(r, "Korunan")
        self.assertEqual(Poll.objects.count(), 0)

    def test_long_option_rejected(self):
        self.client.force_login(self.user)
        self.post(option_1="x" * 101, option_2="B")
        self.assertEqual(Poll.objects.count(), 0)


class PollViewsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="sahip", email="sahip@example.com", password="p")
        self.other = User.objects.create_user(username="baska", email="baska@example.com", password="p")
        self.poll = make_poll(self.owner)

    def test_home_lists_polls_with_username_without_email(self):
        r = self.client.get("/")
        self.assertContains(r, "Sinema mı yemek mi?")
        self.assertContains(r, "@sahip")
        self.assertContains(r, "2 seçenek")
        self.assertNotContains(r, "sahip@example.com")

    def test_home_empty_state(self):
        Poll.objects.all().delete()
        self.assertContains(self.client.get("/"), "Henüz anket yok")

    def test_home_pagination_and_ordering(self):
        for i in range(11):
            make_poll(self.owner, question=f"Soru {i}")
        r = self.client.get("/")
        self.assertEqual(len(r.context["page"]), 10)
        self.assertEqual(r.context["page"][0].question, "Soru 10")
        self.assertEqual(len(self.client.get("/?sayfa=2").context["page"]), 2)

    def test_detail_public(self):
        r = self.client.get(reverse("poll_detail", args=[self.poll.pk]))
        self.assertContains(r, "Sinema")
        self.assertContains(r, "@sahip")
        self.assertNotContains(r, "sahip@example.com")
        self.assertNotContains(r, "Sil")

    def test_detail_404(self):
        self.assertEqual(self.client.get("/anket/9999/").status_code, 404)

    def test_delete_button_only_for_owner(self):
        url = reverse("poll_detail", args=[self.poll.pk])
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(url), "/sil/")
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(url), "/sil/")

    def test_my_polls_requires_login_and_shows_only_own(self):
        make_poll(self.other, question="Başkasının anketi")
        self.assertRedirects(self.client.get("/anketlerim/"), "/giris/?next=/anketlerim/")
        self.client.force_login(self.owner)
        r = self.client.get("/anketlerim/")
        self.assertContains(r, "Sinema mı yemek mi?")
        self.assertNotContains(r, "Başkasının anketi")

    def test_owner_can_delete_with_confirmation(self):
        self.client.force_login(self.owner)
        url = reverse("poll_delete", args=[self.poll.pk])
        self.assertContains(self.client.get(url), "emin misin")
        self.assertEqual(Poll.objects.count(), 1)
        self.assertRedirects(self.client.post(url), "/anketlerim/")
        self.assertEqual(Poll.objects.count(), 0)
        self.assertEqual(Option.objects.count(), 0)

    def test_non_owner_cannot_delete(self):
        self.client.force_login(self.other)
        url = reverse("poll_delete", args=[self.poll.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(Poll.objects.count(), 1)

    def test_guest_cannot_delete(self):
        url = reverse("poll_delete", args=[self.poll.pk])
        self.client.post(url)
        self.assertEqual(Poll.objects.count(), 1)


class VotingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="sahip", email="sahip@example.com", password="p")
        self.poll = make_poll(self.owner, options=("A", "B", "C"))
        self.a, self.b, self.c = self.poll.options.all()
        self.vote_url = reverse("poll_vote", args=[self.poll.pk])
        self.detail_url = reverse("poll_detail", args=[self.poll.pk])

    def vote(self, client, option):
        return client.post(self.vote_url, {"option": option.pk}, follow=True)

    def test_guest_can_vote_once(self):
        r = self.vote(self.client, self.a)
        self.assertRedirects(r, self.detail_url)
        self.assertContains(r, "Oyun kaydedildi!")
        vote = Vote.objects.get()
        self.assertEqual(vote.option, self.a)
        self.assertIsNone(vote.user)
        self.assertTrue(vote.voter_key.startswith("a:"))

    def test_guest_second_vote_rejected(self):
        self.vote(self.client, self.a)
        r = self.vote(self.client, self.b)
        self.assertContains(r, "Bu ankete zaten oy verdin.")
        self.assertEqual(Vote.objects.count(), 1)
        self.assertEqual(Vote.objects.get().option, self.a)

    def test_member_can_vote_once_and_key_is_user_based(self):
        u = User.objects.create_user(username="ali", email="a@example.com", password="p")
        self.client.force_login(u)
        self.vote(self.client, self.b)
        vote = Vote.objects.get()
        self.assertEqual(vote.user, u)
        self.assertEqual(vote.voter_key, f"u:{u.pk}")
        r = self.vote(self.client, self.c)
        self.assertContains(r, "Bu ankete zaten oy verdin.")
        self.assertEqual(Vote.objects.count(), 1)

    def test_member_follows_account_across_browsers(self):
        u = User.objects.create_user(username="ali", email="a@example.com", password="p")
        from django.test import Client
        c1, c2 = Client(), Client()
        c1.force_login(u)
        c2.force_login(u)
        self.vote(c1, self.a)
        self.vote(c2, self.b)
        self.assertEqual(Vote.objects.count(), 1)

    def test_different_browsers_are_different_guests(self):
        from django.test import Client
        self.vote(Client(), self.a)
        self.vote(Client(), self.a)
        self.assertEqual(Vote.objects.count(), 2)

    def test_option_from_other_poll_rejected(self):
        other = make_poll(self.owner, question="Başka", options=("X", "Y"))
        foreign = other.options.first()
        r = self.vote(self.client, foreign)
        self.assertContains(r, "Geçersiz seçenek.")
        self.assertEqual(Vote.objects.count(), 0)

    def test_garbage_option_rejected(self):
        for bad in ["", "abc", "99999", "-1"]:
            self.client.post(self.vote_url, {"option": bad})
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_requires_post(self):
        self.assertEqual(self.client.get(self.vote_url).status_code, 405)

    def test_vote_on_inactive_poll_rejected(self):
        self.poll.is_active = False
        self.poll.save()
        r = self.vote(self.client, self.a)
        self.assertContains(r, "oylamaya kapalı")
        self.assertEqual(Vote.objects.count(), 0)

    def test_detail_shows_vote_buttons_and_no_results_link_before_voting(self):
        r = self.client.get(self.detail_url)
        self.assertContains(r, 'name="option"')
        self.assertNotContains(r, "Oy vermeden sonuçları gör")
        self.assertNotContains(r, "Toplam")
        self.assertContains(r, "Tüm anketler")

    def test_results_hidden_without_voting_even_with_old_query_param(self):
        from django.test import Client
        self.vote(Client(), self.a)
        r = self.client.get(self.detail_url + "?sonuclar=1")
        self.assertContains(r, 'name="option"')
        self.assertNotContains(r, "Toplam")
        self.assertFalse(r.context["show_results"])

    def test_results_percentages_and_counts_after_voting(self):
        from django.test import Client
        for opt in (self.a, self.b):
            self.vote(Client(), opt)
        self.vote(self.client, self.a)
        r = self.client.get(self.detail_url)
        by_text = {o.text: o for o in r.context["options"]}
        self.assertEqual((by_text["A"].vote_count, by_text["A"].percent), (2, 67))
        self.assertEqual((by_text["B"].vote_count, by_text["B"].percent), (1, 33))
        self.assertEqual((by_text["C"].vote_count, by_text["C"].percent), (0, 0))
        self.assertTrue(by_text["A"].is_leader)
        self.assertFalse(by_text["B"].is_leader)
        self.assertEqual(r.context["total_votes"], 3)
        self.assertContains(r, "Toplam 3 oy")

    def test_build_results_with_zero_votes_has_no_leader_and_no_division_error(self):
        from .views import build_results
        options, total = build_results(self.poll)
        self.assertEqual(total, 0)
        self.assertTrue(all(o.percent == 0 and not o.is_leader for o in options))

    def test_voter_sees_results_with_own_choice_marked(self):
        self.vote(self.client, self.b)
        r = self.client.get(self.detail_url)
        self.assertContains(r, "Senin seçimin")
        self.assertNotContains(r, 'name="option"')
        mine = [o for o in r.context["options"] if o.is_mine]
        self.assertEqual([o.text for o in mine], ["B"])

    def test_total_votes_on_home(self):
        from django.test import Client
        self.vote(Client(), self.a)
        self.vote(Client(), self.b)
        self.assertContains(self.client.get("/"), "2 oy")

    def test_vote_survives_user_deletion(self):
        u = User.objects.create_user(username="ali", email="a@example.com", password="p")
        self.client.force_login(u)
        self.vote(self.client, self.a)
        u.delete()
        vote = Vote.objects.get()
        self.assertIsNone(vote.user)


class VoterCookieTests(TestCase):
    def test_cookie_set_on_first_visit_with_flags(self):
        r = self.client.get("/")
        cookie = r.cookies["voter_id"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(int(cookie["max-age"]), 60 * 60 * 24 * 365)
        import uuid
        uuid.UUID(cookie.value)

    def test_cookie_not_reset_when_valid(self):
        self.client.get("/")
        r = self.client.get("/")
        self.assertNotIn("voter_id", r.cookies)

    def test_invalid_cookie_replaced(self):
        self.client.cookies["voter_id"] = "not-a-uuid"
        r = self.client.get("/")
        self.assertIn("voter_id", r.cookies)
        self.assertNotEqual(r.cookies["voter_id"].value, "not-a-uuid")

    def test_first_visit_post_vote_works(self):
        owner = User.objects.create_user(username="s", email="s@example.com", password="p")
        poll = make_poll(owner)
        r = self.client.post(reverse("poll_vote", args=[poll.pk]), {"option": poll.options.first().pk})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Vote.objects.count(), 1)


from django.test import override_settings


class ErrorPageTests(TestCase):
    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_404_page_is_turkish(self):
        r = self.client.get("/olmayan-sayfa/")
        self.assertContains(r, "Sayfa bulunamadı", status_code=404)

    def test_500_template_renders_standalone(self):
        from django.template.loader import render_to_string
        html = render_to_string("500.html")
        self.assertIn("Bir şeyler ters gitti", html)


class DesignSmokeTests(TestCase):
    def test_pages_include_font_and_stylesheet(self):
        r = self.client.get("/")
        self.assertContains(r, "Plus+Jakarta+Sans")
        self.assertContains(r, "css/style.css")
        self.assertContains(r, "js/main.js")

    def test_create_page_loads_poll_form_js(self):
        u = User.objects.create_user(username="ali", email="a@example.com", password="p")
        self.client.force_login(u)
        self.assertContains(self.client.get("/anket/yeni/"), "js/poll_form.js")

    def test_card_accent_cycles_1_to_5(self):
        u = User.objects.create_user(username="ali", email="a@example.com", password="p")
        accents = {make_poll(u, question=str(i)).accent for i in range(10)}
        self.assertEqual(accents, {1, 2, 3, 4, 5})


from unittest import mock

from django.db import connection


class EnableRlsMigrationTests(TestCase):
    def load(self):
        import importlib
        return importlib.import_module("polls.migrations.0003_enable_rls")

    def fake_editor(self, vendor):
        editor = mock.Mock()
        editor.connection.vendor = vendor
        editor.connection.introspection.table_names.return_value = ["accounts_user", "polls_poll"]
        editor.quote_name.side_effect = lambda n: f'"{n}"'
        return editor

    def test_postgres_enables_rls_on_every_table_without_policies(self):
        editor = self.fake_editor("postgresql")
        self.load().enable_rls(None, editor)
        sql = [c.args[0] for c in editor.execute.call_args_list]
        self.assertEqual(sql, [
            'ALTER TABLE "accounts_user" ENABLE ROW LEVEL SECURITY',
            'ALTER TABLE "polls_poll" ENABLE ROW LEVEL SECURITY',
        ])

    def test_reverse_disables_rls(self):
        editor = self.fake_editor("postgresql")
        self.load().disable_rls(None, editor)
        self.assertTrue(all("DISABLE ROW LEVEL SECURITY" in c.args[0] for c in editor.execute.call_args_list))

    def test_sqlite_is_noop(self):
        editor = self.fake_editor("sqlite")
        self.load().enable_rls(None, editor)
        editor.execute.assert_not_called()

    def test_runs_on_current_test_database(self):
        self.assertEqual(connection.vendor, "sqlite")  # testler SQLite ile çalışır; migration no-op geçti
