from django.conf import settings
from django.db import models

MIN_OPTIONS = 2
MAX_OPTIONS = 5


class Poll(models.Model):
    question = models.CharField("soru", max_length=200)
    description = models.TextField("açıklama", max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.question


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField("seçenek", max_length=100)
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.text


class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="votes"
    )
    voter_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["poll", "voter_key"], name="one_vote_per_voter_per_poll"),
        ]

    def __str__(self):
        return f"{self.voter_key} -> {self.option_id}"
