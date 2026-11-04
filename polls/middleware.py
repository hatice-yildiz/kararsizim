import uuid

from django.conf import settings

from .voting import VOTER_COOKIE, VOTER_COOKIE_MAX_AGE, is_valid_uuid


class VoterCookieMiddleware:
    """Anonim seçmenler için kalıcı `voter_id` çerezi (UUID4) oluşturur."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        voter_id = request.COOKIES.get(VOTER_COOKIE)
        is_new = not is_valid_uuid(voter_id)
        if is_new:
            voter_id = str(uuid.uuid4())
        request.voter_id = voter_id.lower()

        response = self.get_response(request)

        if is_new:
            response.set_cookie(
                VOTER_COOKIE,
                request.voter_id,
                max_age=VOTER_COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=not settings.DEBUG,
            )
        return response
