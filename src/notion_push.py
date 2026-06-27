import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

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

NOTION_API_KEY = get_env("NOTION_API_KEY")
NOTION_DATABASE_ID = get_env("NOTION_DATABASE_ID")
NOTION_TITLE_PROPERTY = get_env("NOTION_TITLE_PROPERTY", "이름")

def notion_request(method: str, path: str, payload=None):
    if not NOTION_API_KEY:
        raise RuntimeError("NOTION_API_KEY가 비어 있습니다.")
    if not NOTION_DATABASE_ID:
        raise RuntimeError("NOTION_DATABASE_ID가 비어 있습니다.")

    url = f"https://api.notion.com/v1{path}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code}\n{detail}") from e

def latest_summary_file() -> Path:
    summary_dir = BASE_DIR / "data" / "summaries"
    files = sorted(summary_dir.glob("*_summary.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"요약 파일이 없습니다: {summary_dir}")
    return files[0]

def split_text(text: str, limit: int = 1800):
    text = text.strip()
    if not text:
        return []
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind(" ", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    return [c for c in chunks if c]

def rich_text_array(text: str):
    return [{"type": "text", "text": {"content": text}}]

def line_to_blocks(line: str):
    s = line.strip()
    if not s:
        return []
    block_type = "paragraph"
    content = s
    if s.startswith("### "):
        block_type = "heading_3"
        content = s[4:].strip()
    elif s.startswith("## "):
        block_type = "heading_2"
        content = s[3:].strip()
    elif s.startswith("# "):
        block_type = "heading_1"
        content = s[2:].strip()
    elif s.startswith("- "):
        block_type = "bulleted_list_item"
        content = s[2:].strip()
    elif re.match(r"^\d+\.\s+", s):
        block_type = "numbered_list_item"
        content = re.sub(r"^\d+\.\s+", "", s).strip()

    blocks = []
    for piece in split_text(content, 1800):
        blocks.append({
            "object": "block",
            "type": block_type,
            block_type: {"rich_text": rich_text_array(piece)},
        })
    return blocks

def markdown_to_blocks(markdown_text: str):
    blocks = []
    for line in markdown_text.splitlines():
        blocks.extend(line_to_blocks(line))
    if not blocks:
        blocks = [{
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text_array("내용이 비어 있습니다.")}
        }]
    return blocks

def create_page(title: str):
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            NOTION_TITLE_PROPERTY: {
                "title": rich_text_array(title[:100])
            }
        },
    }
    return notion_request("POST", "/pages", payload)

def append_children(block_id: str, children):
    batch_size = 80
    for i in range(0, len(children), batch_size):
        batch = children[i:i + batch_size]
        notion_request("PATCH", f"/blocks/{block_id}/children", {"children": batch})

def push_markdown(file_path: Path, title: str = ""):
    if not file_path.exists():
        raise FileNotFoundError(f"파일이 없습니다: {file_path}")

    page_title = title.strip() or file_path.stem
    markdown_text = file_path.read_text(encoding="utf-8-sig")
    page = create_page(page_title)
    page_id = page["id"]
    page_url = page.get("url", "")
    blocks = markdown_to_blocks(markdown_text)
    append_children(page_id, blocks)

    print("업로드 완료")
    print(f"- 제목: {page_title}")
    print(f"- 파일: {file_path}")
    print(f"- 블록 수: {len(blocks)}")
    print(f"- Notion URL: {page_url}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, default="")
    parser.add_argument("--title", type=str, default="")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        result = notion_request("GET", f"/databases/{NOTION_DATABASE_ID}")
        print("연결 성공")
        print(result.get("id", ""))
        return

    if args.latest or not args.file:
        target = latest_summary_file()
    else:
        target = Path(args.file).resolve()

    push_markdown(target, args.title)

if __name__ == "__main__":
    main()
