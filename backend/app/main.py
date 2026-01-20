from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
)

from .graph import graph
from .project_config import PROJECT_NAME
from .vector_store import build_vector_store, load_vector_store
from .text_extract import extract_text
from .pmo_db import (
    summarize_project_status,
    save_report_to_db,
    list_reports,
    fetch_report_file,
    get_conn,
)

load_dotenv()

# ==========================================================
# FastAPI App
# ==========================================================
app = FastAPI(title=f"AI Agent - {PROJECT_NAME}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# Models
# ==========================================================
class ChatRequest(BaseModel):
    question: str
    thread_id: str


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    sources: list = []
    graph_flow: list = []


# ==========================================================
# Health / Project Info
# ==========================================================
@app.get("/TALENT")
async def talent():
    return {
        "status": "ok",
        "project": PROJECT_NAME,
    }


# ==========================================================
# Graph Invoke (⭐ 핵심 엔드포인트)
# ==========================================================
@app.post("/graph/invoke", response_model=ChatResponse)
async def graph_invoke(req: ChatRequest):

    # -------------------------------
    # 0️⃣ 초기화
    # -------------------------------
    sources: list = []
    current_turn_sources: list = []

    config = {
        "configurable": {
            "thread_id": req.thread_id
        }
    }

    # -------------------------------
    # 1️⃣ 최초 사용자 메시지
    # -------------------------------
    messages = [HumanMessage(content=req.question)]

    # -------------------------------
    # 2️⃣ LangGraph 실행
    # -------------------------------
    result_state = await graph.ainvoke(
        {"messages": messages},
        config=config,
    )

    messages = result_state["messages"]

    # -------------------------------
    # 3️⃣ 최종 AI 답변 추출
    # -------------------------------
    answer = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content:
            answer = m.content
            break

    # -------------------------------
    # 4️⃣ 이번 턴 메시지 범위 계산
    # -------------------------------
    last_human_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_idx = i
            break

    current_turn_messages = []
    if last_human_idx is not None:
        current_turn_messages = messages[last_human_idx + 1 :]

    # -------------------------------
    # 5️⃣ ToolMessage 기반 source 수집
    # -------------------------------
    for m in current_turn_messages:
        if isinstance(m, ToolMessage):
            try:
                data = json.loads(m.content)

                # vector_search / search_docs 공통 처리
                if isinstance(data, dict) and "documents" in data:
                    for item in data["documents"]:
                        current_turn_sources.append({
                            "source": item.get("source"),
                            "content": item.get("content"),
                        })

                elif isinstance(data, list):
                    for item in data:
                        current_turn_sources.append({
                            "source": item.get("source"),
                            "content": item.get("content"),
                        })

            except Exception:
                pass

    # 중복 제거
    sources = list({
        (s["source"], s["content"]): s
        for s in current_turn_sources
        if s.get("source") and s.get("content")
    }.values())

    # -------------------------------
    # 6️⃣ Tool 사용 여부
    # -------------------------------
    tool_attempted = any(
        isinstance(m, AIMessage) and m.tool_calls
        for m in current_turn_messages
    )

    # -------------------------------
    # 7️⃣ Vector Fallback (ToolMessage 방식)
    # -------------------------------
    vector_fallback_used = False

    if not sources:
        db = load_vector_store()
        if db:
            docs = db.similarity_search(req.question, k=3)

            vector_docs = []
            for d in docs:
                vector_docs.append({
                    "source": d.metadata.get("source", "vector_store"),
                    "content": d.page_content[:800],
                })

            if vector_docs:
                vector_fallback_used = True
                sources = vector_docs

                # ✅ ToolMessage ❌ → HumanMessage ✅
                fallback_context = "\n\n".join(
                    f"[{d['source']}]\n{d['content']}"
                    for d in vector_docs
                )

                messages.append(
                    HumanMessage(
                        content=(
                            "다음은 사내 문서(Vector Store)에서 검색된 참고 자료입니다.\n\n"
                            f"{fallback_context}\n\n"
                            "이 정보를 참고하여 최종 답변을 작성하세요."
                        )
                    )
                )

                # Summarize 재실행
                result_state = await graph.ainvoke(
                    {"messages": messages},
                    config=config,
                )
                messages = result_state["messages"]

                # 최종 답변 재추출
                for m in reversed(messages):
                    if isinstance(m, AIMessage) and m.content:
                        answer = m.content
                        break

    # -------------------------------
    # 8️⃣ Graph Flow 생성
    # -------------------------------
    graph_flow = ["User Question"]

    if tool_attempted:
        graph_flow.append("Agent → Tools")
    else:
        graph_flow.append("Agent Reasoning")

    if vector_fallback_used:
        graph_flow.append("Vector Fallback")

    graph_flow.append("Summarize")

    # -------------------------------
    # 9️⃣ 최종 응답
    # -------------------------------
    print("answer:::::::::::::",answer)
    print("sources:::::::::::::",sources)
    print("graph_flow:::::::::::::",graph_flow)
    return {
        "thread_id": req.thread_id,
        "answer": answer,
        "sources": sources,
        "graph_flow": graph_flow,
    }


# ==========================================================
# Reports / Upload
# ==========================================================
@app.get("/reports")
def report_list():
    return list_reports()


@app.post("/projects/{project_name}/upload-report")
async def upload_report(
    project_name: str,
    file: UploadFile = File(...),
):
    filename = file.filename
    ext = filename.lower().split(".")[-1]

    if ext not in ["pdf", "xlsx", "csv"]:
        raise HTTPException(
            status_code=400,
            detail="PDF 또는 Excel(xlsx,csv)만 업로드 가능합니다",
        )

    binary = await file.read()

    BASE_DIR = Path(__file__).resolve().parent.parent
    UPLOAD_DIR = BASE_DIR / "data" / "pmo_docs"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    save_path = UPLOAD_DIR / filename
    with open(save_path, "wb") as buffer:
        buffer.write(binary)

    texts = extract_text(binary, filename)
    sources = [filename] * len(texts)

    build_vector_store(texts, sources)

    return {
        "status": "accepted",
        "chunks": len(texts),
    }


@app.get("/search")
async def search_docs(question: str = Query(...)):
    db = load_vector_store()
    if not db:
        raise HTTPException(
            status_code=400,
            detail="Vector index not yet created.",
        )

    results = db.similarity_search(question, k=4)
    return [
        {
            "source": d.metadata.get("source", "unknown"),
            "content": d.page_content,
        }
        for d in results
    ]
