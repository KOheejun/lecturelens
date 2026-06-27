from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag_chain import build_chain, load_documents

st.set_page_config(
    page_title="LectureLens RAG",
    page_icon="📚",
    layout="wide",
)

DATA_DIR = ROOT / "data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
SUMMARIES_DIR = DATA_DIR / "summaries"


@st.cache_resource
def get_chain():
    return build_chain()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def get_session_candidates():
    names = set()

    if TRANSCRIPTS_DIR.exists():
        for p in TRANSCRIPTS_DIR.glob("*.txt"):
            names.add(p.stem)

    if SUMMARIES_DIR.exists():
        for p in SUMMARIES_DIR.glob("*.md"):
            names.add(p.stem)

    return sorted(names, reverse=True)


def find_transcript_path(session_name: str) -> Path:
    return TRANSCRIPTS_DIR / f"{session_name}.txt"


def find_summary_path(session_name: str) -> Path:
    return SUMMARIES_DIR / f"{session_name}.md"


def extract_notion_url(text: str) -> str | None:
    match = re.search(r"https://www\.notion\.so/[^\s]+", text)
    return match.group(0) if match else None


def run_notion_push(summary_path: Path, title: str):
    cmd = [
        sys.executable,
        "-m",
        "src.notion_push",
        "--file",
        str(summary_path),
        "--title",
        title,
    ]
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )


if "chat_session_id" not in st.session_state:
    st.session_state.chat_session_id = "web-demo"

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("📚 LectureLens RAG")
st.caption("강의 transcript / summary를 검색해서 근거 기반으로 답하고, summary를 Notion에 저장하는 학습 도우미")

docs = load_documents()
session_names = get_session_candidates()

with st.sidebar:
    st.subheader("상태")
    st.write(f"- 문서 수: {len(docs)}")
    st.write(f"- 세션 수: {len(session_names)}")
    st.text_input("대화 세션 ID", key="chat_session_id")

    if session_names:
        selected_session = st.selectbox("자료 보기 세션", session_names, index=0)
    else:
        selected_session = None
        st.warning("표시할 세션이 없습니다.")

    st.divider()
    st.subheader("Notion 업로드")

    if selected_session:
        selected_summary_path = find_summary_path(selected_session)

        if selected_summary_path.exists():
            st.caption(f"업로드 대상: {selected_summary_path.name}")

            if st.button("현재 세션 Summary 업로드", use_container_width=True):
                with st.spinner("Notion 업로드 중..."):
                    result = run_notion_push(selected_summary_path, selected_session)

                output = (result.stdout or "") + "\n" + (result.stderr or "")
                notion_url = extract_notion_url(output)

                if result.returncode == 0:
                    st.success("Notion 업로드 완료")
                    if notion_url:
                        st.markdown(f"[Notion 페이지 열기]({notion_url})")
                    with st.expander("실행 로그"):
                        st.code(output.strip() or "(로그 없음)")
                else:
                    st.error("Notion 업로드 실패")
                    with st.expander("에러 로그"):
                        st.code(output.strip() or "(로그 없음)")
        else:
            st.warning("이 세션의 summary 파일이 없습니다.")

tab1, tab2 = st.tabs(["💬 RAG 채팅", "📄 자료 보기"])

with tab1:
    if not docs:
        st.error("data/transcripts 또는 data/summaries 에 문서가 없습니다.")
    else:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("sources"):
                    with st.expander("근거 문서"):
                        for s in msg["sources"]:
                            st.write(f"- {s}")

        question = st.chat_input("질문 입력")
        if question:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner("자료 검색 후 답변 생성 중..."):
                    chain = get_chain()
                    result = chain.invoke(
                        {"input": question},
                        config={"configurable": {"session_id": st.session_state.chat_session_id}},
                    )

                    answer = (result.get("answer") or "").strip()
                    context_docs = result.get("context", []) or []
                    sources = sorted({doc.metadata.get("source", "?") for doc in context_docs})

                    st.markdown(answer if answer else "(빈 응답)")
                    if sources:
                        with st.expander("근거 문서"):
                            for s in sources:
                                st.write(f"- {s}")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer if answer else "(빈 응답)",
                    "sources": sources,
                }
            )

with tab2:
    if not selected_session:
        st.info("세션 파일이 없습니다.")
    else:
        transcript_path = find_transcript_path(selected_session)
        summary_path = find_summary_path(selected_session)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Transcript")
            transcript_text = read_text(transcript_path)
            if transcript_text:
                st.text_area(
                    "transcript_text",
                    transcript_text,
                    height=500,
                    label_visibility="collapsed",
                )
            else:
                st.warning("Transcript 파일이 없습니다.")

        with col2:
            st.subheader("Summary")
            summary_text = read_text(summary_path)
            if summary_text:
                st.text_area(
                    "summary_text",
                    summary_text,
                    height=500,
                    label_visibility="collapsed",
                )
            else:
                st.warning("Summary 파일이 없습니다.")
