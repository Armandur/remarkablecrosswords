import json
import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Protocol

import requests as http

from app.config import QUEUE_DIR, REMARKABLE_CLIENT, RMAPI_CONFIG_PATH

logger = logging.getLogger(__name__)


class RemarkableConflictError(Exception):
    """Uppladdning misslyckades för att filen redan finns på reMarkable."""

class RemarkableClient(Protocol):
    def upload(self, pdf_path: Path, remote_folder: str, overwrite: bool = False) -> str: ...
    def ensure_folder(self, path: str) -> bool: ...
    def ls(self, path: str) -> list[str]: ...
    def ls_detailed(self, path: str) -> list[dict]: ...
    def rm(self, path: str) -> bool: ...
    def check(self) -> bool: ...

class RmapiClient:
    def __init__(self):
        self.bin = shutil.which("rmapi")

    def _run(self, *args) -> subprocess.CompletedProcess:
        if not self.bin:
            raise ValueError("rmapi binary not found in PATH")
        env = {**subprocess.os.environ, "RMAPI_FORCE_SCHEMA_VERSION": "4"}
        return subprocess.run([self.bin, *args], capture_output=True, text=True, env=env)

    def check(self) -> bool:
        if not self.bin:
            logger.warning("rmapi binary missing")
            return False
        res = self._run("ls", "/")
        return res.returncode == 0

    def ensure_folder(self, path: str) -> bool:
        # rmapi mkdir -p is not standard, we might need to check and create
        parts = [p for p in path.split("/") if p]
        current = ""
        for part in parts:
            parent = current or "/"
            existing = self.ls(parent)
            current = f"{current}/{part}"
            if part not in existing:
                res = self._run("mkdir", current)
                if res.returncode != 0:
                    return False
        return True

    def ls(self, path: str) -> list[str]:
        res = self._run("ls", path)
        if res.returncode != 0:
            return []
        # rmapi ls output format: [dir] name or [file] name
        lines = res.stdout.splitlines()
        items = []
        for line in lines:
            if "[" in line and "]" in line:
                items.append(line.split("]", 1)[1].strip())
        return items

    def ls_detailed(self, path: str) -> list[dict]:
        res = self._run("ls", path)
        if res.returncode != 0:
            return []
        items = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("[d]"):
                items.append({"name": line[3:].strip(), "is_dir": True})
            elif line.startswith("[f]"):
                items.append({"name": line[3:].strip(), "is_dir": False})
        return items

    def rm(self, path: str) -> bool:
        res = self._run("rm", path)
        return res.returncode == 0

    def upload(self, pdf_path: Path, remote_folder: str, overwrite: bool = False) -> str:
        args = ["put"]
        if overwrite:
            args.append("--force")
        args.extend([str(pdf_path), remote_folder])
        res = self._run(*args)
        if res.returncode != 0:
            if "entry already exists" in res.stderr:
                raise RemarkableConflictError(
                    f"Filen '{pdf_path.stem}' finns redan på reMarkable. "
                    "Aktivera 'Skriv över' för källan om du vill ersätta den."
                )
            raise Exception(f"rmapi upload failed: {res.stderr}")
        return f"{remote_folder}/{pdf_path.name}"

class LocalQueueClient:
    def check(self) -> bool:
        return True

    def ensure_folder(self, path: str) -> bool:
        (QUEUE_DIR / path.lstrip("/")).mkdir(parents=True, exist_ok=True)
        return True

    def ls(self, path: str) -> list[str]:
        p = QUEUE_DIR / path.lstrip("/")
        if not p.exists():
            return []
        return [f.name for f in p.iterdir()]

    def ls_detailed(self, path: str) -> list[dict]:
        p = QUEUE_DIR / path.lstrip("/")
        if not p.exists():
            return []
        return [{"name": f.name, "is_dir": f.is_dir()} for f in sorted(p.iterdir())]

    def rm(self, path: str) -> bool:
        p = QUEUE_DIR / path.lstrip("/")
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
        return True

    def upload(self, pdf_path: Path, remote_folder: str, overwrite: bool = False) -> str:
        target_dir = QUEUE_DIR / remote_folder.lstrip("/")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / pdf_path.name
        shutil.copy2(pdf_path, target_path)
        logger.info(f"PDF queued locally: {target_path}")
        return str(target_path)

def is_rmapi_authenticated() -> bool:
    return RMAPI_CONFIG_PATH.exists() and RMAPI_CONFIG_PATH.stat().st_size > 10

def register_remarkable(code: str) -> tuple[bool, str]:
    """Registrera enhet mot reMarkable cloud med engångskod."""
    device_id = str(uuid.uuid4())
    try:
        r1 = http.post(
            "https://webapp.cloud.remarkable.com/token/json/2/device/new",
            json={"code": code.strip(), "deviceDesc": "desktop-linux", "deviceID": device_id},
            timeout=15,
        )
        if not r1.ok:
            return False, f"Enhetsregistrering misslyckades ({r1.status_code}): {r1.text[:200]}"
        device_token = r1.text.strip()

        r2 = http.post(
            "https://webapp.cloud.remarkable.com/token/json/2/user/new",
            headers={"Authorization": f"Bearer {device_token}"},
            timeout=15,
        )
        if not r2.ok:
            return False, f"Hämtning av användartoken misslyckades ({r2.status_code})"
        user_token = r2.text.strip()

        RMAPI_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        RMAPI_CONFIG_PATH.write_text(json.dumps({"devicetoken": device_token, "usertoken": user_token}))
        return True, "Anslutning till reMarkable lyckades."
    except Exception as e:
        return False, f"Fel: {e}"

def get_remarkable_client() -> RemarkableClient:
    kind = REMARKABLE_CLIENT
    if kind == "local":
        return LocalQueueClient()
    return RmapiClient()
