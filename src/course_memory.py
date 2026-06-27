from pathlib import Path
from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .config import UPSTAGE_API_KEY, OPENAI_BASE_URL, CHAT_MODEL, SUMMARY_DIR


def build_llm():
    if not UPSTAGE_API_KEY:
        raise ValueError("UPSTAGE_API_KEY가 비어 있습니다. .env 파일을 확인해주세요.")

    return ChatOpenAI(
        api_key=UPSTAGE_API_KEY,
        base_url=OPENAI_BASE_URL,
        model=CHAT_MODEL,
        temperature=0.2,
    )


def list_summary_files() -> List[Path]:
    return sorted(SUMMARY_DIR.glob("*_summary.md"), key=lambda p: p.stat().st_mtime)


def load_summaries(limit: int = 20) -> List[dict]:
    files = list_summary_files()[-limit:]
    rows = []

    for f in files:
        try:
            content = f.read_text(encoding="utf-8-sig")
        except Exception:
            content = f.read_text(encoding="utf-8")

        rows.append(
            {
                "name": f.stem,
                "path": str(f),
                "content": content,
            }
        )
    return rows


def _format_summary_context(rows: List[dict]) -> str:
    blocks = []
    for i, row in enumerate(rows, start=1):
        blocks.append(
            f"[세션 {i}]"
            f"\n이름={row['name']}"
            f"\n내용=\n{row['content']}"
        )
    return "\n\n".join(blocks)


def build_course_memory(limit: int = 20) -> str:
    rows = load_summaries(limit=limit)
    if not rows:
        return "요약 파일이 아직 없습니다."

    llm = build_llm()
    prompt = ChatPromptTemplate.from_template(
        """
너는 여러 강의 세션을 묶어서 학습 흐름을 정리하는 학습 코치다.

아래 여러 세션 요약을 보고 다음 형식으로 정리하라.

출력 형식:
# 누적 학습 메모리

## 1. 지금까지 반복해서 등장한 핵심 개념
- 3~6개 bullet

## 2. 현재까지의 큰 흐름
- 4~6문장

## 3. 아직 불명확하거나 더 공부가 필요한 부분
- 3개 bullet

## 4. 다음 학습 방향 제안
- 사용자의 실제 학습 흐름을 바탕으로 3개 제안
- '멘토 추천' 같은 표현 금지
- 지금까지 배운 내용에서 자연스럽게 이어지는 방향만 제안

세션 요약들:
{context}
"""
    )
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"context": _format_summary_context(rows)})


def build_next_direction(limit: int = 20) -> str:
    rows = load_summaries(limit=limit)
    if not rows:
        return "요약 파일이 아직 없습니다."

    llm = build_llm()
    prompt = ChatPromptTemplate.from_template(
        """
너는 이전 강의 기록을 바탕으로 다음 학습 방향을 제안하는 학습 코치다.

중요 규칙:
- 사용자가 실제로 지금까지 배운 내용에서 이어지는 방향만 제안
- 외부에서 임의로 주제를 끌어오지 말 것
- '멘토 추천' 같은 표현 금지
- 각 제안은 왜 지금 시점에 필요한지 짧게 설명

출력 형식:
## 다음 방향 3가지
1. 방향 이름
- 왜 이게 다음 단계인지
- 어떤 질문으로 공부를 이어가면 좋은지

2. 방향 이름
- 왜 이게 다음 단계인지
- 어떤 질문으로 공부를 이어가면 좋은지

3. 방향 이름
- 왜 이게 다음 단계인지
- 어떤 질문으로 공부를 이어가면 좋은지

세션 요약들:
{context}
"""
    )
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"context": _format_summary_context(rows)})
