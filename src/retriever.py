import re
from typing import List
from langchain_core.documents import Document

def _tokenize(text: str) -> List[str]:
    return re.findall(r"[0-9A-Za-z가-힣]+", text.lower())

def build_windows(documents: List[Document], window_size: int = 3, stride: int = 2) -> List[Document]:
    if not documents:
        return []

    windows: List[Document] = []
    i = 0

    while i < len(documents):
        chunk = documents[i:i + window_size]
        if not chunk:
            break

        content = " ".join(doc.page_content for doc in chunk).strip()
        if not content:
            i += stride
            continue

        start_ts = chunk[0].metadata.get("start_ts", "")
        end_ts = chunk[-1].metadata.get("end_ts", "")
        source = chunk[0].metadata.get("source", "")

        windows.append(
            Document(
                page_content=content,
                metadata={
                    "source": source,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "start_line": chunk[0].metadata.get("line_no"),
                    "end_line": chunk[-1].metadata.get("line_no"),
                },
            )
        )

        i += stride

    return windows

def _score(question: str, content: str) -> float:
    q_tokens = set(_tokenize(question))
    c_tokens = set(_tokenize(content))

    if not q_tokens or not c_tokens:
        return 0.0

    overlap = q_tokens.intersection(c_tokens)
    score = float(len(overlap))

    if question.strip() and question.strip() in content:
        score += 3.0

    return score

def retrieve_relevant_chunks(question: str, documents: List[Document], top_k: int = 4) -> List[Document]:
    windows = build_windows(documents)
    if not windows:
        return []

    ranked = []
    for doc in windows:
        s = _score(question, doc.page_content)
        ranked.append((s, doc))

    ranked.sort(key=lambda x: x[0], reverse=True)

    positive = [doc for score, doc in ranked if score > 0]
    if positive:
        return positive[:top_k]

    return [doc for _, doc in ranked[:top_k]]
