from fastapi.templating import Jinja2Templates
from app.database import get_db
from app.auth import get_current_user, require_admin

templates = Jinja2Templates(directory="app/templates")
