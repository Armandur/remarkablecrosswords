import base64
import logging
import urllib.request
from .base import FieldSpec

logger = logging.getLogger(__name__)

class NtfyNotifier:
    KIND = "ntfy"
    LABEL = "ntfy"
    CONFIG_FIELDS = [
        FieldSpec(
            name="server",
            label="Server",
            type="text",
            placeholder="https://ntfy.sh",
            default="https://ntfy.sh",
            help_text="URL till ntfy-servern",
            options=None,
        ),
        FieldSpec(
            name="topic",
            label="Ämne (Topic)",
            type="text",
            placeholder="mitt-amne",
            default="",
            help_text="Namnet på kanalen/ämnet",
            options=None,
        ),
        FieldSpec(
            name="auth_type",
            label="Autentisering",
            type="select",
            placeholder=None,
            default="none",
            help_text="Typ av autentisering",
            options=[
                {"value": "none", "label": "Ingen"},
                {"value": "token", "label": "Access Token"},
                {"value": "password", "label": "Användarnamn/Lösenord"},
            ],
        ),
        FieldSpec(
            name="token",
            label="Access Token",
            type="text",
            placeholder=None,
            default="",
            help_text="Access Token (för token-autentisering)",
            options=None,
        ),
        FieldSpec(
            name="username",
            label="Användarnamn",
            type="text",
            placeholder=None,
            default="",
            help_text="Användarnamn (för lösenords-autentisering)",
            options=None,
        ),
        FieldSpec(
            name="password",
            label="Lösenord",
            type="password",
            placeholder=None,
            default="",
            help_text="Lösenord (för lösenords-autentisering)",
            options=None,
        ),
    ]

    def __init__(self, config: dict):
        if "url" in config and "topic" not in config:
            self.url = config["url"]
        else:
            server = config.get("server", "https://ntfy.sh").rstrip("/")
            topic = config.get("topic", "")
            self.url = f"{server}/{topic}"
        self.auth_type = config.get("auth_type", "none")
        self.token = config.get("token", "")
        self.username = config.get("username", "")
        self.password = config.get("password", "")

    def send(self, title: str, message: str, click_url: str | None = None) -> bool:
        try:
            headers = {"Title": title.encode("utf-8")}
            if click_url:
                headers["Click"] = click_url
            if self.auth_type == "token" and self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            elif self.auth_type == "password" and self.username:
                creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                headers["Authorization"] = f"Basic {creds}"
            req = urllib.request.Request(self.url, data=message.encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req) as resp:
                return resp.status == 200
        except Exception as e:
            logger.exception(f"Failed to send ntfy notification to {self.url}: {e}")
            return False
