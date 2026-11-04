import uuid

VOTER_COOKIE = "voter_id"
VOTER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def get_voter_key(request):
    """Giriş yapmışsa "u:<id>", anonimse çerezdeki UUID ile "a:<uuid>"."""
    if request.user.is_authenticated:
        return f"u:{request.user.pk}"
    return f"a:{request.voter_id}"


def is_valid_uuid(value):
    try:
        return str(uuid.UUID(value)) == value.lower()
    except (ValueError, AttributeError, TypeError):
        return False
