import pandas as pd
import streamlit as st
from datetime import datetime

def parse_dates_safe(series):
    known_formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y",
        "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d %H%M",
        "%Y/%m/%d %H%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"
    ]
    def try_parse(val):
        if pd.isna(val): return pd.NaT
        for fmt in known_formats:
            try:
                return datetime.strptime(str(val), fmt)
            except:
                continue
        try:
            return pd.to_datetime(val, errors='coerce')
        except:
            return pd.NaT
    return series.apply(try_parse)

st.title("🧬 NICU KONIS 혈액배양-중환자실 매칭")

icu_file = st.file_uploader("중환자실 입퇴실 파일 업로드", type=['xlsx'])
culture_file = st.file_uploader("혈액배양 양성 파일 업로드", type=['xlsx'])

if icu_file and culture_file:
    icu_df = pd.read_excel(icu_file)
    culture_df = pd.read_excel(culture_file)

    st.markdown("### 🔍 컬럼 선택")

    icu_id = st.selectbox("중환자실 ID", icu_df.columns)
    icu_in = st.selectbox("입실일", icu_df.columns)
    icu_out = st.selectbox("퇴실일", icu_df.columns)

    culture_id = st.selectbox("혈액배양 ID", culture_df.columns)
    culture_date = st.selectbox("혈액배양일", culture_df.columns)

    if st.button("🔁 매칭 실행"):
        icu_df[icu_in] = parse_dates_safe(icu_df[icu_in])
        icu_df[icu_out] = parse_dates_safe(icu_df[icu_out])
        culture_df[culture_date] = parse_dates_safe(culture_df[culture_date])

        merged = culture_df.merge(
            icu_df[[icu_id, icu_in, icu_out]],
            left_on=culture_id,
            right_on=icu_id,
            how='left'
        )

        matched = merged[
            (merged[culture_date] >= merged[icu_in]) &
            (merged[culture_date] <= merged[icu_out])
        ]

        result = culture_df.merge(
            matched[[culture_id, culture_date, icu_in, icu_out]],
            on=[culture_id, culture_date],
            how='left'
        )

        st.success("매칭 완료! 결과 미리보기:")
        st.dataframe(result)

        st.download_button("📥 결과 다운로드", data=result.to_excel(index=False, engine='openpyxl'), file_name="matched_result.xlsx")

