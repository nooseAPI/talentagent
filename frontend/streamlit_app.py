import uuid
import requests
import streamlit as st
from collections import Counter
import pandas as pd
import re

API_BASE = "http://localhost:8000"

# ===============================
# Page Config
# ===============================
st.set_page_config(
    page_title="사내 TALENT AI 비서",
    page_icon="📊",
    layout="wide"
)

# ===============================
# Project Name
# ===============================
project_name = "사내 TALENT AI 비서"
try:
    resp = requests.get(f"{API_BASE}/talent", timeout=5)
    if resp.ok:
        project_name = resp.json().get("project", project_name)
except Exception:
    pass

st.title(project_name)

# ===============================
# Intro
# ===============================
st.markdown(
    """
이 서비스는 **Talent (Talent Analytics & AI Transformation)** 기반으로  
사내 **인재·역량·채용·성과·학습·커리어** 전 영역을 지원하는 **AI 인재 비서**입니다.

### 🔹 주요 지원 영역
- 📌 **채용·배치**: 직무-스킬 적합도 분석, 내부 인재 추천
- 📌 **역량 관리**: 개인/조직 스킬 현황 요약 및 격차 분석
- 📌 **성과·이탈 분석**: 성과 요인 분석, 이탈 리스크 시그널
- 📌 **학습·커리어**: 개인 맞춤 업스킬·커리어 패스 제안
- 📌 **HR 정책·규정**: 인사 규정, 평가·보상 기준 질의응답
---
### 💬 예시 질문
- "이 직무에 필요한 핵심 스킬 Top 5는 뭐야?"
- "현재 우리 팀의 스킬 갭은 어디에 있어?"
- "이 직원에게 추천할 다음 커리어 경로는?"
- "입사 1~2년 차 이탈 위험 신호를 알려줘"
- "역량 기반 평가 기준을 정리해줘"
- "사내 데이터로 Talent 대시보드 구성안 만들어줘"
"""
)

# ===============================
# Session State
# ===============================
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# ===============================
# Sidebar
# ===============================
with st.sidebar:
    st.subheader("🧵 세션 정보")
    st.code(st.session_state.thread_id, language="bash")

    if st.button("🔄 대화 초기화"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.subheader("📤 보고서 업로드")

    uploaded_file = st.file_uploader(
        "PDF 또는 Excel(XLSX) 파일 선택",
        type=["pdf", "xlsx"]
    )

    if uploaded_file:
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type
            )
        }

        url = f"{API_BASE}/projects/{project_name}/upload-report"
        resp = requests.post(url, files=files)

        if resp.ok:
            st.success("파일 업로드 완료")
        else:
            st.error(resp.text)

# ===============================
# Chat History
# ===============================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ===============================
# Chat Input
# ===============================
if prompt := st.chat_input("질문을 입력하세요"):
    # -------------------------------
    # User message
    # -------------------------------
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    # -------------------------------
    # Graph Invoke (ONLY ENTRY POINT)
    # -------------------------------
    sources = []
    graph_flow = []
    answer = ""
    try:
        payload = {
            "question": prompt,
            "thread_id": st.session_state.thread_id
        }

        resp = requests.post(
            f"{API_BASE}/graph/invoke",
            json=payload,
            timeout=420
        )
        print("resp:::::::::::",resp)
        resp.raise_for_status()

        data = resp.json()
        answer = data.get("answer", "")
        sources = data.get("sources", [])
        graph_flow = data.get("graph_flow", [])
        #graph_flow = st.session_state.get("graph_flow") or []
        print("data:::::::::::",data)
        print("answer:::::::::::",answer)
        print("sources:::::::::::",sources)
        print("graph_flow1111111:::::::::::",graph_flow)

        st.session_state.graph_flow = graph_flow
    except Exception as e:
        print("sourcesException:::::::::::",sources)
        answer = f"⚠️ AI 처리 중 오류 발생\n\n`{e}`"
        sources = []
        graph_flow = None

    # -------------------------------
    # messages에 저장
    # -------------------------------
    st.session_state.messages.append(
        {"role": "assistant", "content": answer}
    )
    # -------------------------------
    # Assistant Output
    # -------------------------------
    with st.chat_message("assistant"):
        st.markdown(answer or "✅ 분석을 완료했습니다.")

    # -------------------------------
    # Graph Flow
    # -------------------------------
    print("graph_flow2222222:::::::::::",graph_flow)
    if graph_flow and any(
        step in graph_flow for step in ("Agent → Tools", "Vector Fallback")
    ):
        print("1111111111111")
        st.subheader("🧭 AI 처리 흐름")

        mermaid = "graph LR\n"
        for i in range(len(graph_flow) - 1):
            mermaid += f"  {graph_flow[i]} --> {graph_flow[i+1]}\n"

        st.markdown(
            f"""
            ```mermaid
            {mermaid}
            """,
            unsafe_allow_html=True
            )
        
        # ===============================
        # 📊 Role 별 인원수 Bar Chart
        # ===============================
        if sources:
            st.subheader("🧑‍💼 직무(Role)별 인원 분포")

            roles = []

            for s in sources:
                content = s.get("content", "")
                match = re.search(r"role:\s*([^\n]+)", content)
                if match:
                    roles.append(match.group(1).strip())

            if roles:
                df_roles = pd.DataFrame.from_dict(
                    Counter(roles),
                    orient="index",
                    columns=["count"]
                ).sort_values("count", ascending=False)

                st.bar_chart(df_roles)
            else:
                st.caption("직무(role) 정보가 발견되지 않았습니다.")
            
    else:
        print("22222222222222")
        st.caption("ℹ️ 이번 질문에는 Tool 호출이 필요하지 않았습니다.")
        # -------------------------------
        # Sources
        # -------------------------------
        if sources:
            st.subheader("📑 참고 문서")
            for s in sources:
                with st.expander(f"📄 {s.get('source', 'document')}"):
                    st.markdown(s.get("content", ""))


