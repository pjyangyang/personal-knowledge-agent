from openai import OpenAI

from ..config import settings
from ..schemas import CitationRead


INSUFFICIENT_EVIDENCE = "当前知识库中没有找到足够资料，无法可靠回答该问题。"


def generate_answer(question: str, citations: list[CitationRead]) -> str:
    if not citations:
        return INSUFFICIENT_EVIDENCE
    if not settings.llm_api_key or not settings.llm_model:
        context = "\n".join(
            f"[{index}] {item.filename} 第 {item.page_number} 页：{item.quote}"
            for index, item in enumerate(citations, start=1)
        )
        return f"已找到 {len(citations)} 条相关资料。尚未配置大语言模型，以下是检索证据：\n\n{context}"

    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    evidence = "\n\n".join(
        f"[{index}] 文件：{item.filename}；页码：{item.page_number}\n原文：{item.quote}"
        for index, item in enumerate(citations, start=1)
    )
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个严格依据资料回答的知识库助手。只能使用用户提供的证据，不得使用外部知识。"
                    "每个重要结论后必须标注对应的引用编号，例如[1]。如果证据不足，必须回答："
                    f"“{INSUFFICIENT_EVIDENCE}”不得编造页码、文件名、事实或引用。"
                ),
            },
            {
                "role": "user",
                "content": f"问题：{question}\n\n可用证据：\n{evidence}",
            },
        ],
    )
    answer = response.choices[0].message.content
    return answer.strip() if answer else INSUFFICIENT_EVIDENCE
