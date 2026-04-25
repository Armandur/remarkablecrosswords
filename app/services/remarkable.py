import logging
import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from app.config import QUEUE_DIR, REMARKABLE_CLIENT

logger = logging.getLogger(__name__)

class RemarkableClient(Protocol):
    def upload(self, pdf_path: Path, remote_folder: str) -> str:
        ...
    def ensure_folder(self, path: str) -> bool:
        ...
    def ls(self, path: str) -> list[str]:
        ...
    def check(self) -> bool:
        ...

class RmapiClient:
    def __init__(self):
        self.bin = shutil.which("rmapi")

    def _run(self, *args) -> subprocess.CompletedProcess:
        if not self.bin:
            raise ValueError("rmapi binary not found in PATH")
        return subprocess.run([self.bin, *args], capture_output=True, text=True)

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

    def upload(self, pdf_path: Path, remote_folder: str) -> str:
        res = self._run("put", str(pdf_path), remote_folder)
        if res.returncode != 0:
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

    def upload(self, pdf_path: Path, remote_folder: str) -> str:
        target_dir = QUEUE_DIR / remote_folder.lstrip("/")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / pdf_path.name
        shutil.copy2(pdf_path, target_path)
        logger.info(f"PDF queued locally: {target_path}")
        return str(target_path)

def get_remarkable_client() -> RemarkableClient:
    kind = REMARKABLE_CLIENT
    if kind == "local":
        return LocalQueueClient()
    return RmapiClient()
