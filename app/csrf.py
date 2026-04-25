from fastapi import Request, HTTPException, Form
from itsdangerous import URLSafeSerializer
from app.config import SESSION_SECRET_KEY

_s = URLSafeSerializer(SESSION_SECRET_KEY, salt='csrf')

def generate_csrf_token(request: Request) -> str:
    user_id = request.session.get('user_id', 'anon')
    return _s.dumps(str(user_id))

def validate_csrf_token(request: Request, token: str) -> bool:
    user_id = request.session.get('user_id', 'anon')
    try:
        return _s.loads(token) == str(user_id)
    except Exception:
        return False

class CsrfProtect:
    async def __call__(self, request: Request, csrf_token: str = Form(default='')):
        if not validate_csrf_token(request, csrf_token):
            raise HTTPException(status_code=403, detail='Ogiltigt CSRF-token')
        return True
