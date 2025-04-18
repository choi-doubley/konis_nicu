import pandas as pd
import streamlit as st
from datetime import datetime
import io

# 날짜 파싱 함수
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

# 앱 시작
st.title("🧬 NICU KONIS 혈액배양-중환자실 매칭")

# 파일 업로드
icu_file = st.file_uploader("중환자실 입퇴실 파일 업로드", type=['xlsx'])
culture_file = st.file_uploader("혈액배양 양성 파일 업로드", type=['xlsx'])

# 파일 둘 다 업로드되었을 때 실행
if icu_file and culture_file:
    icu_df = pd.read_excel(icu_file)
    culture_df = pd.read_excel(culture_file)

    st.markdown("### 🔍 컬럼 선택")

    # 사용자에게 컬럼 선택시키기
    icu_id = st.selectbox("중환자실 ID", icu_df.columns)
    icu_in = st.selectbox("입실일", icu_df.columns)
    icu_out = st.selectbox("퇴실일", icu_df.columns)

    culture_id = st.selectbox("혈액배양 ID", culture_df.columns)
    culture_date = st.selectbox("혈액배양일", culture_df.columns)

    if st.button("🔁 매칭 실행"):
        # 날짜 파싱
        icu_df[icu_in] = parse_dates_safe(icu_df[icu_in])
        icu_df[icu_out] = parse_dates_safe(icu_df[icu_out])
        culture_df[culture_date] = parse_dates_safe(culture_df[culture_date])

        # merge
        merged = culture_df.merge(
            icu_df[[icu_id, icu_in, icu_out]],
            left_on=culture_id,
            right_on=icu_id,
            how='left'
        )

        # 날짜 필터
        matched = merged[
            (merged[culture_date] >= merged[icu_in]) &
            (merged[culture_date] <= merged[icu_out])
        ]

        # 최종 결과: 원본 culture_df에 입실일/퇴실일만 붙이기
        result = culture_df.merge(
            matched[[culture_id, culture_date, icu_in, icu_out]],
            on=[culture_id, culture_date],
            how='left'
        )

        st.success("매칭 완료! 결과 미리보기:")
        st.dataframe(result)

        # 엑셀 다운로드용 버퍼 만들기
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            result.to_excel(writer, index=False)
        output.seek(0)

        st.download_button(
            label="📥 결과 다운로드",
            data=output,
            file_name="matched_result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
