from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

TRANSCRIPT_DIR = BASE_DIR / "data" / "transcripts"
SUMMARY_DIR = BASE_DIR / "data" / "summaries"

TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)


def _parse_env_file(path: Path):
    data = {}
    if not path.exists():
        return data

    text = path.read_text(encoding="utf-8-sig")

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue
        if line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            data[key] = value

    return data


_FILE_ENV = _parse_env_file(ENV_PATH)


def _pick_env(name: str, default: str = "") -> str:
    os_value = str(os.environ.get(name, "")).strip()
    file_value = str(_FILE_ENV.get(name, "")).strip()

    if os_value:
        return os_value
    if file_value:
        return file_value
    return default


UPSTAGE_API_KEY = _pick_env("UPSTAGE_API_KEY", "")
OPENAI_BASE_URL = _pick_env("OPENAI_BASE_URL", "https://api.upstage.ai/v1")
CHAT_MODEL = _pick_env("CHAT_MODEL", "solar-pro2")
SESSION_ID = _pick_env("SESSION_ID", "demo_session")
