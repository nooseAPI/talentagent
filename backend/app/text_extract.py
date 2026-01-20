import os
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook


def extract_text(binary: bytes, filename: str):
    ext = os.path.splitext(filename)[1].lower()
    print("변환 시작 :::"+ext)
    print("binary :::", binary)
    print(binary[:0])
    print(binary[:1])
    print(binary[:2])
    print(binary[:3])

    if ext == ".xlsx":
        if is_valid_xlsx(binary):
            df = pd.read_excel(BytesIO(binary), engine="openpyxl")
        else:
            # CSV fallback
            try:
                df = pd.read_csv(BytesIO(binary))
            except Exception:
                raise ValueError("엑셀 형식이 아닙니다. 올바른 XLSX 또는 CSV 파일을 업로드하세요.")

    elif ext == ".csv":
        df = pd.read_csv(BytesIO(binary))

    else:
        raise ValueError("지원하지 않는 파일 형식")

    return convert_df_to_texts(df)


def is_valid_xlsx(binary):
    try:
        load_workbook(BytesIO(binary), read_only=True)
        return True
    except Exception:
        return False


def convert_df_to_texts(df: pd.DataFrame) -> list[str]:
    """
    엑셀/CSV DataFrame을 벡터 인덱스용 텍스트 리스트로 변환.
    - 완전히 비어있는 행은 제거
    - 각 행: "컬럼명: 값" 형식으로 줄바꿈하여 하나의 텍스트로 만듦
    """
    # 완전히 빈 행은 제거
    df = df.dropna(how="all")

    texts: list[str] = []

    for _, row in df.iterrows():
        cells = []

        for col, value in row.items():
            # NaN, None 등은 스킵
            if pd.isna(value):
                continue
            cells.append(f"{col}: {value}")

        # 내용이 있는 행만 텍스트로 추가
        if cells:
            text = "\n".join(cells)
            texts.append(text)

    return texts
