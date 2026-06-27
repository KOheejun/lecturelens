import re
from pathlib import Path
from typing import List
from langchain_core.documents import Document

LINE_PATTERN = re.compile(r"^\[(?P<start>.*?)\s~\s(?P<end>.*?)\]\s(?P<text>.*)$")

def load_transcript_txt(file_path: str) -> List[Document]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일이 없습니다: {path}")

    text = path.read_text(encoding="utf-8-sig")
    docs: List[Document] = []

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        match = LINE_PATTERN.match(line)
        if match:
            start_ts = match.group("start").strip()
            end_ts = match.group("end").strip()
            content = match.group("text").strip()
        else:
            start_ts = ""
            end_ts = ""
            content = line

        if not content:
            continue

        docs.append(
            Document(
                page_content=content,
                metadata={
                    "source": str(path),
                    "line_no": line_no,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                },
            )
        )

    return docs
