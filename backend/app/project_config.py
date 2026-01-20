from pathlib import Path
from functools import lru_cache
from datetime import date
from langchain_core.tools import tool
from .pmo_db import fetch_project, fetch_milestones, summarize_project_status


# 🔽 ID/이름을 PMO 비서용으로 변경
PROJECT_ID = "p02_talent_assistant"
PROJECT_NAME = "사내 TALENT AI 비서"

# 🔽 시스템 프롬프트를 PMO 도메인으로 변경
SYSTEM_PROMPT = """너는 회사의 인사 데이터, 역량 정보, 프로젝트 이력,
사내 규정 문서를 기반으로 임직원의 질문에 답하는
'TALENT AX (Talent Analytics & AI Transformation) AI 비서'다.

다음 원칙을 반드시 지켜라.

1) 모든 답변은 반드시 한국어 존댓말로 작성한다.
2) 사용자가 직무나 분야를 명시하지 않은 경우,
   기본적으로 '일반 IT/사무직 기준'으로 가정하여 설명한다.
   - 이 가정은 답변 첫 줄에 명확히 밝힌다.
3) 문서, 데이터, Tool 결과에 근거하지 않은 내용은 추측하지 않는다.
   - 알 수 없는 경우 '현재 제공된 데이터 기준으로는 확인할 수 없습니다.'라고 말한다.
4) 답변은 항상 실무에 바로 활용 가능한 형태로 제공한다.
   - 목록, 단계, 표 형식 우선
5) Tool을 통해 분석한 경우,
   답변 하단에 '관련 근거' 섹션을 추가한다.
   - 문서명, 데이터 출처, 핵심 내용 bullet 1~3개
6) 질문이 모호한 경우에도,
   불필요하게 되묻지 말고 합리적인 가정을 기반으로 먼저 답변한다.
"""

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "hr_policies"


@lru_cache()
def load_docs():
    docs = []
    for path in sorted(DATA_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines:
            continue
        title = lines[0].lstrip("#").strip()
        docs.append(
            {
                "title": title,
                "path": path.name,
                "content": text,
            }
        )
    return docs


@tool
def search_docs(query: str) -> str:
    """사내 인사/복지/근태/보안 규정 문서에서 질의와 관련된 내용을 찾아 반환합니다."""
    query_norm = query.strip().lower()
    docs = load_docs()

    if not docs:
        return "현재 로드된 문서가 없습니다. 관리자가 데이터를 추가해야 합니다."

    if not query_norm:
        summaries = []
        for d in docs:
            summaries.append(
                f"[{d['title']} / {d['path']}]\n"
                f"{d['content'][:200]}..."
            )
        return "\n\n".join(summaries)

    scored = []
    for d in docs:
        content_lower = d["content"].lower()
        score = content_lower.count(query_norm)
        if query_norm in d["title"].lower():
            score += 3
        if score > 0:
            scored.append((score, d))

    if not scored:
        return "현재 제공된 샘플 데이터에서 관련 정보를 찾지 못했습니다. 키워드를 바꿔 다시 시도해 주세요."

    scored.sort(key=lambda x: x[0], reverse=True)
    top_docs = [d for _, d in scored[:3]]

    snippets = []
    for d in top_docs:
        lines = d["content"].splitlines()
        body_lines = lines[1:]
        hit_lines = [
            ln.strip()
            for ln in body_lines
            if query_norm in ln.lower()
        ]
        if not hit_lines:
            hit_lines = [ln.strip() for ln in body_lines[:3]]
        snippet = "\n".join(hit_lines[:5])
        snippets.append(
            f"[{d['title']} / {d['path']}]\n{snippet}"
        )

    return "\n\n".join(snippets)


@tool
def analyze_project_status(project_name: str) -> str:
    """
    실제 PMO DB의 프로젝트, 마일스톤 데이터를 분석하여
    일정 리스크 상태를 텍스트로 요약합니다.
    """

    row = fetch_project(project_name)

    if not row:
        return f"DB에 '{project_name}' 프로젝트가 존재하지 않습니다."

    pid, name, manager, progress = row

    milestones = fetch_milestones(pid)

    today = date.today()

    delayed = []
    upcoming = []

    for title, due_str, status in milestones:
        due = date.fromisoformat(due_str)

        if status != "DONE" and due < today:
            delta = (today - due).days
            delayed.append(f"{title}: {delta}일 지연")
        elif 0 <= (due - today).days <= 14:
            upcoming.append(f"{title}: {due} 예정")

    lines = []
    lines.append(f"📊 프로젝트: {name}")
    lines.append(f"담당 PM: {manager}")
    lines.append(f"진행률: {progress}%")

    if delayed:
        lines.append("\n🚨 지연 마일스톤")
        lines.extend(f" - {x}" for x in delayed)

    if upcoming:
        lines.append("\n📌 2주 이내 예정 마일스톤")
        lines.extend(f" - {x}" for x in upcoming)

    if not delayed and not upcoming:
        lines.append("\n일정 특이 사항 없음")

    if delayed or progress < 60:
        risk = "HIGH"
    elif upcoming or progress < 70:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    lines.append(f"\n⚠ 종합 리스크 등급: {risk}")

    return "\n".join(lines)