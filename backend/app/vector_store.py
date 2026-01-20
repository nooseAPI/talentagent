from pathlib import Path
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# =========================
# 경로 고정
# =========================
BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "vector_index"
INDEX_PATH.mkdir(parents=True, exist_ok=True)

# =========================
# Ollama Embeddings (OpenAI 완전 제거)
# =========================
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://localhost:11434"
)

# =========================
# Text Splitter
# =========================
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100
)

# =========================
# Vector Index 생성
# =========================
def build_vector_store(texts: list[str], sources: list[str]):
    try:
        docs: list[Document] = []

        print("sources::::", sources)

        for text, src in zip(texts, sources):
            if not text.strip():
                continue

            chunks = text_splitter.split_text(text)

            for c in chunks:
                docs.append(
                    Document(
                        page_content=c,
                        metadata={"source": src}
                    )
                )

        if not docs:
            print("⚠️ VECTOR BUILD SKIPPED — docs empty")
            return

        print("VECTOR DOC COUNT:", len(docs))
        print("EMBEDDINGS TYPE:", type(embeddings))
        db = FAISS.from_documents(docs, embeddings)
        db.save_local(str(INDEX_PATH))

        print("✅ VECTOR INDEX BUILD COMPLETE")

    except Exception as e:
        print("❌ VECTOR BUILD ERROR =>", e)


# =========================
# Vector Index 로드
# =========================
def load_vector_store():
    if not INDEX_PATH.exists():
        print("⚠️ VECTOR INDEX NOT FOUND")
        return None

    return FAISS.load_local(
        str(INDEX_PATH),
        embeddings,
        allow_dangerous_deserialization=True
    )
