import os
from pathlib import Path
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

# =========================
# 경로 설정
# =========================

BASE_DIR = Path(__file__).resolve().parent
VECTOR_PATH = BASE_DIR / "vector_index"
VECTOR_PATH.mkdir(exist_ok=True)

# =========================
# Ollama Embeddings (전역)
# =========================

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://localhost:11434"
)

# =========================
# 신규 Vector Index 생성
# =========================

def build_vector_index(texts: List[str], sources: List[str]):
    documents = []

    for t, s in zip(texts, sources):
        documents.append(
            Document(
                page_content=t,
                metadata={"source": s}
            )
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )

    chunks = splitter.split_documents(documents)

    print("EMBEDDINGS TYPE:", type(embeddings))
    print("📁 VECTOR INDEX DIR:", str(VECTOR_PATH))
    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(str(VECTOR_PATH))

    print("✅ vector_index 최초 생성 완료")


# =========================
# Vector Index 생성 or 업데이트
# =========================

def build_or_update_vector_index(texts: List[str]):
    faiss_file = VECTOR_PATH / "index.faiss"

    if faiss_file.exists():
        print("🔁 기존 vector_index 로드 후 업데이트")
        db = FAISS.load_local(
            str(VECTOR_PATH),
            embeddings,
            allow_dangerous_deserialization=True
        )
        db.add_texts(texts)
    else:
        print("🆕 신규 vector_index 생성")
        db = FAISS.from_texts(texts, embeddings)

    db.save_local(str(VECTOR_PATH))
    print("✅ vector_index 저장 완료")
