import os
from pathlib import Path

from langchain_openai import ChatOpenAI

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
SUMMARY_DIR = BASE_DIR / "data" / "summaries"

def read_env_file(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data

_FILE_ENV = read_env_file(ENV_PATH)

def get_env(name: str, default: str = "") -> str:
    os_value = os.getenv(name, "").strip()
    if os_value:
        return os_value
    return _FILE_ENV.get(name, default).strip()

def read_text(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            pass
    return path.read_text(errors="ignore")

def build_llm():
    api_key = get_env("UPSTAGE_API_KEY")
    base_url = get_env("OPENAI_BASE_URL", "https://api.upstage.ai/v1")
    model = get_env("CHAT_MODEL", "solar-pro2")

    if not api_key:
        raise RuntimeError("UPSTAGE_API_KEY가 비어 있습니다.")

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0.2,
    )

def load_recent_summaries(current_name: str, max_sessions: int = 5) -> str:
    if not SUMMARY_DIR.exists():
        return ""
    files = sorted(SUMMARY_DIR.glob("*_summary.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    blocks = []
    count = 0
    for path in files:
        if current_name in path.stem:
            continue
        text = read_text(path).strip()
        if not text:
            continue
        blocks.append(f"[이전 세션: {path.stem}]\n{text[:2200]}")
        count += 1
        if count >= max_sessions:
            break
    return "\n\n".join(blocks)

def generate_learning_coach_report(current_name: str, transcript_text: str, summary_text: str) -> str:
    llm = build_llm()
    recent_context = load_recent_summaries(current_name=current_name, max_sessions=5)

    prompt = f"""
너는 LectureLens의 AI 학습 코치다.

규칙:
- 멘토식 일반론 말고, 제공된 학습 기록만 근거로 말해라.
- 과장하지 말고 짧고 실용적으로 써라.
- 근거가 약하면 '근거 부족'이라고 써라.
- 반드시 한국어로 답해라.
- 아래 형식을 정확히 지켜라.

출력 형식:
## 1. 현재 강의 핵심
- 3줄 이내

## 2. 이전 기록과 연결되는 개념
- 2~4개 bullet

## 3. 지금 보강이 필요한 개념
- 2~3개 bullet
- 각 항목마다 이유 1줄

## 4. 다음 학습 방향
- 바로 할 일 3개
- 짧은 행동 문장으로

## 5. 바로 물어볼 질문
- 3개 bullet

## 6. 1주 미니 플랜
- Day 1
- Day 2
- Day 3

[현재 세션 이름]
{current_name}

[현재 강의 요약]
{summary_text[:4000] if summary_text else "요약 없음"}

[현재 강의 전사 일부]
{transcript_text[:4000] if transcript_text else "전사 없음"}

[이전 세션 요약]
{recent_context if recent_context else "이전 세션 없음"}
""".strip()

    result = llm.invoke(prompt)
    return result.content if hasattr(result, "content") else str(result)
