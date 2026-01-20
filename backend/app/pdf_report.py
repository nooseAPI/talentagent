from pathlib import Path
from textwrap import wrap

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)


# 한글 폰트 등록
def register_korean_font():
    font_path = r"C:\Windows\Fonts\malgun.ttf"

    pdfmetrics.registerFont(
        TTFont("Malgun", font_path)
    )


def create_weekly_report_pdf(project_name: str, body_text: str) -> Path:
    register_korean_font()  # ✅ 반드시 setFont 전에 호출

    safe_name = "".join(c if c.isalnum() else "_" for c in project_name)
    pdf_path = REPORT_DIR / f"weekly_report_{safe_name}.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    margin_x = 40
    y = height - 60

    # 제목
    c.setFont("Malgun", 16)
    c.drawString(margin_x, y, f"PMO 주간 보고서 - {project_name}")
    y -= 40

    # 본문
    c.setFont("Malgun", 11)
    max_chars = 70

    for line in body_text.splitlines():
        if not line.strip():
            y -= 18
            continue

        for wrapped in wrap(line, max_chars):
            if y < 60:
                c.showPage()
                c.setFont("Malgun", 11)   # ✅ 페이지 넘어갈 때도 폰트 유지
                y = height - 60

            c.drawString(margin_x, y, wrapped)
            y -= 16

    c.showPage()
    c.save()

    return pdf_path
