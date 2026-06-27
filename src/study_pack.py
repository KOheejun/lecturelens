import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

TRANSCRIPT_DIR = BASE_DIR / "data" / "transcripts"
SUMMARY_DIR = BASE_DIR / "data" / "summaries"
LOG_DIR = BASE_DIR / "data" / "logs"
PACK_DIR = BASE_DIR / "data" / "study_packs"
MISCONCEPTION_LOG_PATH = LOG_DIR / "misconception_log.json"


def ensure_dirs():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PACK_DIR.mkdir(parents=True, exist_ok=True)


def read_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
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


def read_text(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            pass
    return path.read_text(errors="ignore")


def latest_transcript_file() -> Path:
    files = sorted(TRANSCRIPT_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"전사 txt 파일이 없습니다: {TRANSCRIPT_DIR}")
    return files[0]


def summary_for_transcript(transcript_path: Path) -> Path:
    return SUMMARY_DIR / f"{transcript_path.stem}_summary.md"


def latest_pair() -> tuple:
    transcript = latest_transcript_file()
    summary = summary_for_transcript(transcript)
    if not summary.exists():
        raise FileNotFoundError(f"summary 파일이 없습니다: {summary}")
    return transcript, summary


def extract_json_array(text: str) -> List[Dict[str, Any]]:
    text = text.strip()
    if not text:
        return []

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except Exception:
        pass

    match = re.search(r"\[\s*{.*}\s*\]", text, re.S)
    if not match:
        return []

    try:
        data = json.loads(match.group(0))
        if isinstance(data, list):
            return data
    except Exception:
        return []

    return []


def load_log() -> List[Dict[str, Any]]:
    if not MISCONCEPTION_LOG_PATH.exists():
        return []
    try:
        data = json.loads(read_text(MISCONCEPTION_LOG_PATH))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_log(items: List[Dict[str, Any]]):
    MISCONCEPTION_LOG_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def generate_study_pack_text(llm, session_name: str, transcript_text: str, summary_text: str) -> str:
    prompt = f"""
너는 강의 복습용 study pack 생성기다.

규칙:
- 제공된 전사/요약 범위 안에서만 작성해라.
- 추측하지 말고 불확실하면 '기록 부족'이라고 써라.
- 반드시 한국어로 작성해라.
- 아래 형식을 정확히 따라라.

출력 형식:
# Study Pack - {session_name}

## 1. 오늘 강의 핵심
- 3~5개 bullet

## 2. 핵심 개념 정리
- 개념명: 짧은 설명
- 3~5개

## 3. 헷갈릴 수 있는 부분
- 2~4개 bullet
- 왜 헷갈릴 수 있는지 1줄씩

## 4. 복습 질문
- 3개 번호 목록

## 5. 바로 할 행동
- 3개 bullet

## 6. 시험 전 한 줄 암기 포인트
- 2~3개 bullet

[강의 요약]
{summary_text[:5000] if summary_text else "요약 없음"}

[강의 전사]
{transcript_text[:7000] if transcript_text else "전사 없음"}
""".strip()

    result = llm.invoke(prompt)
    return result.content if hasattr(result, "content") else str(result)


def generate_misconceptions(llm, session_name: str, transcript_text: str, summary_text: str) -> List[Dict[str, Any]]:
    prompt = f"""
너는 강의 복습용 오개념 추출기다.

목표:
- 이 강의에서 학습자가 헷갈릴 가능성이 높은 개념을 2~5개 뽑아라.
- 반드시 제공된 기록에 근거해야 한다.
- JSON 배열만 출력해라.
- 코드블록 금지, 설명문 금지.

JSON 형식:
[
  {{
    "concept": "개념명",
    "why_confusing": "왜 헷갈리는지",
    "recommended_action": "어떻게 복습하면 좋은지",
    "severity": "low|medium|high"
  }}
]

[강의 요약]
{summary_text[:5000] if summary_text else "요약 없음"}

[강의 전사]
{transcript_text[:7000] if transcript_text else "전사 없음"}
""".strip()

    result = llm.invoke(prompt)
    raw = result.content if hasattr(result, "content") else str(result)
    return extract_json_array(raw)


def save_study_pack(session_name: str, content: str) -> Path:
    out_path = PACK_DIR / f"{session_name}_study_pack.md"
    out_path.write_text(content, encoding="utf-8-sig")
    return out_path


def append_misconception_log(session_name: str, misconceptions: List[Dict[str, Any]]) -> Path:
    log_items = load_log()
    now = datetime.now(timezone.utc).isoformat()

    for item in misconceptions:
        if not isinstance(item, dict):
            continue
        log_items.append(
            {
                "session": session_name,
                "created_at": now,
                "concept": str(item.get("concept", "")).strip(),
                "why_confusing": str(item.get("why_confusing", "")).strip(),
                "recommended_action": str(item.get("recommended_action", "")).strip(),
                "severity": str(item.get("severity", "medium")).strip() or "medium",
            }
        )

    save_log(log_items)
    return MISCONCEPTION_LOG_PATH


def process_session(transcript_path: Path, summary_path: Path):
    ensure_dirs()

    transcript_text = read_text(transcript_path).strip()
    summary_text = read_text(summary_path).strip()
    session_name = transcript_path.stem

    llm = build_llm()

    study_pack_text = generate_study_pack_text(
        llm=llm,
        session_name=session_name,
        transcript_text=transcript_text,
        summary_text=summary_text,
    )
    study_pack_path = save_study_pack(session_name, study_pack_text)

    misconceptions = generate_misconceptions(
        llm=llm,
        session_name=session_name,
        transcript_text=transcript_text,
        summary_text=summary_text,
    )
    log_path = append_misconception_log(session_name, misconceptions)

    print("생성 완료")
    print(f"- session: {session_name}")
    print(f"- study_pack: {study_pack_path}")
    print(f"- misconception_log: {log_path}")
    print(f"- misconception_count: {len(misconceptions)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--file", type=str, default="")
    parser.add_argument("--summary", type=str, default="")
    args = parser.parse_args()

    if args.latest or not args.file:
        transcript_path, summary_path = latest_pair()
    else:
        transcript_path = Path(args.file).resolve()
        summary_path = Path(args.summary).resolve() if args.summary else summary_for_transcript(transcript_path)

    if not transcript_path.exists():
        raise FileNotFoundError(f"전사 파일이 없습니다: {transcript_path}")
    if not summary_path.exists():
        raise FileNotFoundError(f"요약 파일이 없습니다: {summary_path}")

    process_session(transcript_path, summary_path)


if __name__ == "__main__":
    main()
