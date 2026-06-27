from pathlib import Path
from langchain_openai import ChatOpenAI
from .config import UPSTAGE_API_KEY, OPENAI_BASE_URL, CHAT_MODEL, SUMMARY_DIR


def chunk_text(text: str, chunk_size: int = 1800, overlap: int = 200):
    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        if end == n:
            break
        start = end - overlap

    return chunks


def build_llm():
    if not UPSTAGE_API_KEY:
        raise ValueError("UPSTAGE_API_KEY가 비어 있습니다. .env 파일에 넣어주세요.")

    return ChatOpenAI(
        api_key=UPSTAGE_API_KEY,
        base_url=OPENAI_BASE_URL,
        model=CHAT_MODEL,
        temperature=0.2,
    )


def summarize_text(text: str) -> str:
    llm = build_llm()
    chunks = chunk_text(text)
    partial_summaries = []

    for i, chunk in enumerate(chunks, start=1):
        prompt = f"""
다음은 강의 전사 일부입니다.
핵심만 한국어로 정리하세요.

형식:
- 핵심 내용:
- 중요한 개념:
- 다시 볼 포인트:

전사:
{chunk}
"""
        resp = llm.invoke(prompt)
        partial_summaries.append(f"[파트 {i}]\n{resp.content}")

    merged = "\n\n".join(partial_summaries)

    final_prompt = f"""
아래는 강의 부분 요약들입니다.
이를 바탕으로 최종 강의 요약을 한국어로 작성하세요.

형식:
1. 한 줄 핵심요약
2. 핵심 개념 3~5개
3. 다시 봐야 할 부분 3개
4. 전체 흐름 요약 4~6문장

부분 요약:
{merged}
"""
    final_resp = llm.invoke(final_prompt)
    return final_resp.content


def summarize_file(file_name: str) -> Path:
    file_path = Path(file_name)
    if not file_path.exists():
        raise FileNotFoundError(f"파일이 없습니다: {file_path}")

    text = file_path.read_text(encoding="utf-8-sig")
    summary = summarize_text(text)

    out_path = SUMMARY_DIR / f"{file_path.stem}_summary.md"
    out_path.write_text(summary, encoding="utf-8-sig")
    return out_path

