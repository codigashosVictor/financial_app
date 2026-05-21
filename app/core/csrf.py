import secrets
from hmac import compare_digest

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

CSRF_SESSION_KEY = "csrf_token"
CSRF_HEADER = "x-csrf-token"
CSRF_FORM_FIELD = "csrf_token"


def get_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def configure_templates(templates: Jinja2Templates) -> Jinja2Templates:
    templates.env.globals["csrf_token"] = get_csrf_token
    return templates


async def verify_csrf(request: Request) -> None:
    expected = request.session.get(CSRF_SESSION_KEY)
    provided = request.headers.get(CSRF_HEADER)

    if not provided:
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            form = await request.form()
            provided = form.get(CSRF_FORM_FIELD)

    if not expected or not provided or not compare_digest(str(expected), str(provided)):
        raise HTTPException(status_code=403, detail="CSRF token inválido")
