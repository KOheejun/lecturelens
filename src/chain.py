from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .config import UPSTAGE_API_KEY, OPENAI_BASE_URL, CHAT_MODEL

def build_llm():
    if not UPSTAGE_API_KEY:
        raise ValueError("UPSTAGE_API_KEY가 비어 있습니다. .env 파일을 확인해주세요.")

    return ChatOpenAI(
        api_key=UPSTAGE_API_KEY,
        base_url=OPENAI_BASE_URL,
        model=CHAT_MODEL,
        temperature=0.2,
    )

def format_context(docs: List[Document]) -> str:
    lines = []
    for i, doc in enumerate(docs, start=1):
        start_ts = doc.metadata.get("start_ts", "")
        end_ts = doc.metadata.get("end_ts", "")
        source = doc.metadata.get("source", "")

        lines.append(
            f"[문맥 {i}]"
            f"\nsource={source}"
            f"\n시간={start_ts} ~ {end_ts}"
            f"\n내용={doc.page_content}"
        )

    return "\n\n".join(lines)

def answer_question(question: str, docs: List[Document]) -> str:
    if not docs:
        return "관련 전사 구간을 찾지 못했습니다."

    llm = build_llm()

    prompt = ChatPromptTemplate.from_template(
        """
너는 강의 전사 기반 학습 코치다.
사용자의 질문은 단순 정의 질문일 수도 있고,
'내가 이해한 게 ~인데 맞아?' 같은 이해 검증 질문일 수도 있다.

중요 규칙:
- 반드시 제공된 문맥 안에서만 판단하라.
- 문맥에 없는 내용은 추측하지 말고 '기록에서 확인되지 않음'이라고 말하라.
- 사용자의 이해가 맞는지 평가할 때는 맞는 부분 / 부족한 부분 / 다른 부분을 구분해서 설명하라.
- 답변은 한국어로 짧고 선명하게 작성하라.
- 근거 구간에는 반드시 시간 정보를 사용하라.

출력 형식:
### 1. 판정
- 맞음 / 대체로 맞음 / 부분적으로 맞음 / 다름 / 기록에서 확인되지 않음
- 한 줄 설명

### 2. 근거 구간
- 시간대와 함께 2~4개 bullet
- 각 bullet은 해당 구간에서 무엇을 말하는지 짧게 설명

### 3. 보정 설명
- 사용자의 이해에서 맞는 부분
- 빠졌거나 수정이 필요한 부분
- 강의 기준으로 더 적절한 표현 1문장

### 4. 한 줄 암기 포인트
- 시험 직전 보듯 한 줄로 정리

사용자 질문:
{question}

문맥:
{context}
"""
    )

    chain = prompt | llm | StrOutputParser()
    return chain.invoke(
        {
            "question": question,
            "context": format_context(docs),
        }
    )
