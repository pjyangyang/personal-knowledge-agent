from openai import OpenAI

from ..config import settings
from ..schemas import CitationRead
from ..skills.registry import SkillDefinition, get_skill


INSUFFICIENT_EVIDENCE = "当前知识库中没有找到足够资料，无法可靠回答该问题。"


def generate_answer(question: str, citations: list[CitationRead], skill: SkillDefinition | None = None) -> str:
    skill = skill or get_skill("general_qa")
    if not citations:
        return INSUFFICIENT_EVIDENCE
    if not settings.llm_api_key or not settings.llm_model:
        context = "\n".join(
            f"[{index}] {item.filename} 第 {item.page_number} 页：{item.quote}"
            for index, item in enumerate(citations, start=1)
        )
        return f"[{skill.name}] 已找到 {len(citations)} 条相关资料。尚未配置大语言模型，以下是检索证据：\n\n{context}"

    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        messages=build_messages(question, citations, skill),
    )
    answer = response.choices[0].message.content
    return answer.strip() if answer else INSUFFICIENT_EVIDENCE


def stream_answer(question: str, citations: list[CitationRead], skill: SkillDefinition | None = None):
    skill = skill or get_skill("general_qa")
    if not citations or not settings.llm_api_key or not settings.llm_model:
        yield generate_answer(question, citations, skill)
        return
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    stream = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        messages=build_messages(question, citations, skill),
        stream=True,
    )
    for chunk in stream:
        content = chunk.choices[0].delta.content if chunk.choices else None
        if content:
            yield content


def build_messages(question: str, citations: list[CitationRead], skill: SkillDefinition) -> list[dict[str, str]]:
    evidence = "\n\n".join(
        f"[{index}] 文件：{item.filename}；页码：{item.page_number}\n原文：{item.quote}"
        for index, item in enumerate(citations, start=1)
    )
    return [
        {
            "role": "system",
            "content": (
                f"你正在执行 Skill：{skill.name}。\n{skill.system_prompt}\n"
                "无论 Skill 如何要求，都只能使用用户提供的证据，不得使用外部知识。"
                "每个重要结论后必须标注对应的引用编号，例如[1]。如果证据不足，必须回答："
                f"“{INSUFFICIENT_EVIDENCE}”不得编造页码、文件名、事实或引用。"
            ),
        },
        {"role": "user", "content": f"问题：{question}\n\n可用证据：\n{evidence}"},
    ]
