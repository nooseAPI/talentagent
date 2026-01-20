import sqlite3
from pathlib import Path
from datetime import date
from datetime import datetime


DB_FILE = Path(__file__).parent / "pmo.db"


def get_conn():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # 기존 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        manager TEXT,
        progress INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS milestones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        title TEXT,
        due_date TEXT,
        status TEXT
    )
    """)

    # ✅ 파일 저장 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT,
        file_type TEXT,
        file_name TEXT,
        created_at TEXT,
        data BLOB
    )
    """)

    conn.commit()
    conn.close()


#def seed_data():
#    conn = get_conn()
#    cur = conn.cursor()

    # 프로젝트
#    cur.execute("""
#    INSERT INTO projects(name, manager, progress)
#    VALUES ('차세대 로그인 시스템 구축', '홍길동', 65)
#    """)

#    pid = cur.lastrowid

#    milestones = [
#        (pid, "요구사항 정의", "2025-01-31", "DONE"),
#        (pid, "설계 완료", "2025-02-15", "DONE"),
#        (pid, "개발 완료", "2025-03-10", "IN_PROGRESS"),
#        (pid, "통합 테스트", "2025-03-25", "NOT_STARTED"),
#    ]

#    cur.executemany("""
#    INSERT INTO milestones(project_id,title,due_date,status)
#    VALUES (?,?,?,?)
#    """, milestones)

#    conn.commit()
#    conn.close()


def fetch_project(name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, manager, progress FROM projects WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    return row


def fetch_milestones(project_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT title, due_date, status
    FROM milestones WHERE project_id = ?
    """, (project_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def summarize_project_status(project_name: str) -> str:
    """
    프로젝트/마일스톤 정보를 조회해
    일정 및 리스크 상태를 한국어 텍스트로 요약.
    PDF 생성과 LangChain Tool에서 공통 사용.
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
            delayed.append(f"{title}: {delta}일 지연 (상태: {status})")
        elif 0 <= (due - today).days <= 14:
            upcoming.append(f"{title}: {due} 예정 (상태: {status})")

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

    # 간단 리스크 룰
    if delayed or progress < 60:
        risk = "HIGH"
    elif upcoming or progress < 70:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    lines.append(f"\n⚠ 종합 리스크 등급: {risk}")

    return "\n".join(lines)


def save_report_to_db(project_name: str, file_type: str, file_path: Path):
    import sqlite3

    conn = get_conn()
    cur = conn.cursor()

    with open(file_path, "rb") as f:
        binary = f.read()

    cur.execute("""
        INSERT INTO reports(project_name, file_type, file_name, created_at, data)
        VALUES (?, ?, ?, ?, ?)
    """, (
        project_name,
        file_type,
        file_path.name,
        datetime.now().isoformat(timespec="seconds"),
        binary
    ))

    conn.commit()
    conn.close()


def fetch_report_file(report_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT file_name, data FROM reports WHERE id=?", (report_id,))
    row = cur.fetchone()

    conn.close()
    return row


def list_reports():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, project_name, file_type, file_name, created_at
        FROM reports
        ORDER BY created_at DESC
    """)

    rows = cur.fetchall()
    conn.close()
    return rows