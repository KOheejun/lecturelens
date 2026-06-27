from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_upstage import ChatUpstage, UpstageEmbeddings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
SUMMARIES_DIR = DATA_DIR / "summaries"

_store: Dict[str, BaseChatMessageHistory] = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in _store:
        _store[session_id] = InMemoryChatMessageHistory()
    return _store[session_id]


def load_documents() -> List[Document]:
    docs: List[Document] = []

    if TRANSCRIPTS_DIR.exists():
        for path in sorted(TRANSCRIPTS_DIR.glob("*.txt")):
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": path.name,
                            "kind": "transcript",
                            "path": str(path),
                            "session": path.stem,
                        },
                    )
                )

    if SUMMARIES_DIR.exists():
        for path in sorted(SUMMARIES_DIR.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": path.name,
                            "kind": "summary",
                            "path": str(path),
                            "session": path.stem,
                        },
                    )
                )

    return docs


def build_chain():
    load_dotenv()

    if not os.getenv("UPSTAGE_API_KEY"):
        raise RuntimeError("UPSTAGE_API_KEY 가 .env 에 없습니다.")

    docs = load_documents()
    if not docs:
        raise RuntimeError("data/transcripts 또는 data/summaries 에 문서가 없습니다.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    embeddings = UpstageEmbeddings(model="solar-embedding-1-large")
    vectorstore = InMemoryVectorStore(embeddings)
    vectorstore.add_documents(chunks)

    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    model_name = os.getenv("CHAT_MODEL", "solar-pro")
    llm = ChatUpstage(model=model_name, temperature=0.2)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """너는 LectureLens 학습 코치다.
반드시 검색된 문서(context)에 근거해서만 답해라.
문서에 없는 내용은 추측하지 말고 "자료에 없음"이라고 말해라.

답변 형식:
1. 핵심 답변
2. 근거 2~4개
3. 내가 놓쳤을 가능성이 큰 개념 1~2개
4. 다음 공부 행동 1개

context:
{context}
""",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ]
    )

    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, combine_docs_chain)

    chain_with_history = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )

    return chain_with_history


def ask(question: str, session_id: str = "default") -> None:
    chain = build_chain()
    result = chain.invoke(
        {"input": question},
        config={"configurable": {"session_id": session_id}},
    )

    answer = result.get("answer", "").strip()
    context_docs = result.get("context", []) or []
    sources = sorted({doc.metadata.get("source", "?") for doc in context_docs})

    print("\n=== ANSWER ===\n")
    print(answer if answer else "(빈 응답)")
    print("\n=== SOURCES ===")
    for s in sources:
        print(f"- {s}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--q", required=True, help="질문")
    parser.add_argument("--session", default="default", help="대화 세션 ID")
    args = parser.parse_args()

    ask(args.q, args.session)


if __name__ == "__main__":
    main()
