# backend/app/build_vector_index.py

import os
from pathlib import Path
import pandas as pd

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

# =========================
# 기본 설정
# =========================

# 현재 파일: backend/app/build_vector_index.py
# BASE_DIR = backend
BASE_DIR = Path(__file__).resolve().parent.parent

# 엑셀 위치
DATA_FILE = BASE_DIR / "data" / "pmo_docs" / "TALENT_AX_Sample.xlsx"

# 인덱스 저장 위치
INDEX_DIR = BASE_DIR / "app" / "vector_index"
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# 엑셀 → 텍스트 변환
# =========================

def load_excel_documents(excel_path: Path) -> list[str]:
    """엑셀을 읽어서 각 행을 하나의 문장으로 합친 리스트 반환"""
    if not excel_path.exists():
        raise FileNotFoundError(f"엑셀 파일을 찾을 수 없습니다: {excel_path}")

    df = pd.read_excel(excel_path)

    texts: list[str] = []
    for _, row in df.iterrows():
        row_text = " | ".join(
            f"{col}: {row[col]}" for col in df.columns
        )
        texts.append(row_text)

    return texts


# =========================
# Vector Index 생성
# =========================

def build_vector_index() -> None:
    print("📄 Excel 파일 경로:", DATA_FILE)

    texts = load_excel_documents(DATA_FILE)
    print(f"✅ 엑셀 로드 완료 (row 수: {len(texts)})")

    # 텍스트 chunk 분할
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )

    chunks: list[str] = []
    for t in texts:
        chunks.extend(splitter.split_text(t))

    print(f"✂️ 분할된 chunk 개수: {len(chunks)}")

    docs = [
        Document(
            page_content=chunk,
            metadata={"source": DATA_FILE.name},
        )
        for chunk in chunks
    ]

    # =========================
    # Ollama Embeddings
    # =========================

    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434",  # 기본값 (명시 권장)
    )

    print("🧠 Ollama 임베딩 생성 및 FAISS 인덱스 구축 중...")
    print("EMBEDDINGS TYPE:", type(embeddings))
    db = FAISS.from_documents(docs, embeddings)
    db.save_local(INDEX_DIR)

    
    print("\n✅ VECTOR INDEX 생성 완료!")
    print("📁 저장 위치:", INDEX_DIR.resolve())
    print("   - index.faiss")
    print("   - index.pkl")


if __name__ == "__main__":
    build_vector_index()
