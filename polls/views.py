"""Eski "Kararsızım" anketleri: yalnızca okunur arşiv. Oylama, oluşturma ve silme kaldırıldı;
veriler (anketler, seçenekler, oylar) olduğu gibi korunur."""
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from .models import Poll


def legacy_list(request):
    polls = (
        Poll.objects.select_related("created_by")
        .annotate(option_count=Count("options", distinct=True), total_votes=Count("votes", distinct=True))
        .order_by("-created_at", "-pk")
    )
    page = Paginator(polls, 12).get_page(request.GET.get("sayfa"))
    return render(request, "polls/legacy_list.html", {"page": page})


def legacy_detail(request, pk):
    poll = get_object_or_404(Poll.objects.select_related("created_by"), pk=pk)
    options = list(poll.options.annotate(vote_count=Count("votes")))
    total = sum(o.vote_count for o in options)
    top = max((o.vote_count for o in options), default=0)
    for o in options:
        o.percent = round(o.vote_count * 100 / total) if total else 0
        o.is_leader = top > 0 and o.vote_count == top
    return render(request, "polls/legacy_detail.html", {"poll": poll, "options": options, "total_votes": total})
