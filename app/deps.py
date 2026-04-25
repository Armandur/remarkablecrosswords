from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.database import get_db
from app.auth import get_current_user, require_admin
from app.csrf import generate_csrf_token

class CsrfTemplates(Jinja2Templates):
    def TemplateResponse(
        self,
        request: Request,
        name: str,
        context: dict | None = None,
        **kwargs
    ):
        if context is None:
            context = {}
        context["csrf_token"] = generate_csrf_token(request)
        return super().TemplateResponse(request, name, context, **kwargs)

templates = CsrfTemplates(directory="app/templates")
