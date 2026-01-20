from __future__ import annotations

from typing import Annotated, List, Literal
from typing_extensions import TypedDict

# ✅ deprecation 방지: langchain-ollama 사용 권장
from langchain_ollama import ChatOllama

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessage,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from .project_config import SYSTEM_PROMPT, search_docs, analyze_project_status


# =========================
# State
# =========================
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


# =========================
# Tools
# =========================
tools = [search_docs, analyze_project_status]
tool_node = ToolNode(tools)


# =========================
# Ollama LLM
#  - num_predict: 응답 길이 제한(타임아웃 방지)
#  - num_ctx: 컨텍스트 제한(폭증 방지)
# =========================
agent_llm = ChatOllama(
    model="qwen2.5:3b",
    base_url="http://localhost:11434",
    temperature=0,
    num_ctx=4096,
    num_predict=512,  # ⭐ 중요: 응답 길이 제한
).bind_tools(tools)   # ⭐ 중요: tool_calls 생성 가능하게


# =========================
# Routing
#  - tool_calls 있으면 tools로
#  - 없으면 summarize로 종료
# =========================
def route_after_agent(state):
    last_msg = state["messages"][-1]

    # tool 호출이 있으면 tools 노드로
    if getattr(last_msg, "tool_calls", None):
        return "tools"

    # tool 호출이 없으면 요약 후 종료
    return "summarize"


# =========================
# Nodes
# =========================
async def agent_node(state: AgentState) -> AgentState:
    # Agent는 tool을 호출할지/말지 판단
    response = await agent_llm.ainvoke(state["messages"])
    return {"messages": [response]}


async def summarize_node(state: AgentState) -> AgentState:
    """
    ⭐ 타임아웃 방지 핵심:
    - messages 전체를 그대로 재주입하지 말고 "최근 N개"만 사용
    - tool 결과(검색 문서)는 이미 messages에 포함될 수 있으니,
      너무 길면 요약 프롬프트로 압축 유도
    """
    messages = state["messages"]

    # 최근 대화만 사용 (컨텍스트 폭증 방지)
    recent = messages[-12:]  # 필요시 8~16 사이로 조절

    # 사용자 질문(첫 HumanMessage) 추출
    user_question = ""
    for m in messages:
        if isinstance(m, HumanMessage):
            user_question = m.content
            break

    system_msg = SystemMessage(content=SYSTEM_PROMPT.strip())

    # 최종 정리 지시
    human_msg = HumanMessage(
        content=(
            "아래 대화와 tool 결과를 바탕으로 최종 답변을 작성하세요.\n\n"
            f"사용자 질문: {user_question}\n\n"
            "형식:\n"
            "1) 요약 답변: 핵심 3~6문장\n"
            "2) 추가 안내: 주의 포인트 1~3개\n"
            "3) 참고 정보: 참고 문서/근거 bullet 2~4개\n\n"
            "주의: 불필요한 장문 생성 금지. 간결하고 실무적으로 작성."
        )
    )

    # summarize는 tool 바인딩 없이도 되지만, 동일 모델 재사용
    # (num_predict 제한 덕에 길어지지 않음)
    response = await agent_llm.ainvoke([system_msg] + recent + [human_msg])
    return {"messages": [response]}


# =========================
# Graph
# =========================
builder = StateGraph(AgentState)

builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)
builder.add_node("summarize", summarize_node)

builder.add_edge(START, "agent")
builder.add_conditional_edges(
    "agent",
    route_after_agent,
    {
        "tools": "tools",
        "summarize": "summarize",
    },
)
builder.add_edge("tools", "agent")
builder.add_edge("summarize", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
