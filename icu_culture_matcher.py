import pandas as pd
import streamlit as st
from datetime import datetime
import io

# 날짜 자동 인식 함수
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
st.set_page_config(page_title="NICU KONIS Matcher", layout="centered")
st.title("NICU KONIS 혈액배양양성 - 중환자실입퇴실일 매칭 앱")

# 파일 업로드
icu_file = st.file_uploader("📄 중환자실 입퇴실 파일 업로드 (.xlsx)", type=['xlsx'])
culture_file = st.file_uploader("📄 혈액배양 양성 파일 업로드 (.xlsx)", type=['xlsx'])

if icu_file and culture_file:
    icu_df = pd.read_excel(icu_file)
    culture_df = pd.read_excel(culture_file)

    st.subheader("🔧 컬럼 선택")

    # ICU 컬럼
    icu_id = st.selectbox("중환자실 ID 컬럼", icu_df.columns)
    icu_in = st.selectbox("입실일 컬럼", icu_df.columns)
    icu_out = st.selectbox("퇴실일 컬럼", icu_df.columns)

    # 혈액배양 컬럼
    culture_id = st.selectbox("혈액배양 ID 컬럼", culture_df.columns)
    culture_date = st.selectbox("혈액배양일 컬럼", culture_df.columns)

    if st.button("🔁 매칭 실행"):
        # 날짜 파싱
        icu_df[icu_in] = parse_dates_safe(icu_df[icu_in])
        icu_df[icu_out] = parse_dates_safe(icu_df[icu_out])
        culture_df[culture_date] = parse_dates_safe(culture_df[culture_date])

        # ID 기준 merge
        merged = culture_df.merge(
            icu_df[[icu_id, icu_in, icu_out]],
            left_on=culture_id,
            right_on=icu_id,
            how='left'
        )

        # 캘린더 데이로 변환
        merged['culture_date_day'] = merged[culture_date].dt.date
        merged['icu_in_day'] = merged[icu_in].dt.date
        merged['icu_out_day'] = merged[icu_out].dt.date

        # 입실 3일째 = 입실일 + 2일, 퇴실 2일째 = 퇴실일 + 1일
        merged['icu_day_start'] = merged['icu_in_day'] + pd.Timedelta(days=2)
        merged['icu_day_end'] = merged['icu_out_day'] + pd.Timedelta(days=1)

        # 조건 만족하는 행만 필터
        matched = merged[
            (merged['culture_date_day'] >= merged['icu_day_start']) &
            (merged['culture_date_day'] <= merged['icu_day_end'])
        ]

        # culture_df 기준으로 left join (ICU 정보 붙이기)
        result = culture_df.merge(
            matched[[culture_id, culture_date, icu_in, icu_out]],
            on=[culture_id, culture_date],
            how='left'
        )

        # 결과 출력 및 다운로드
        st.success("✅ 매칭 완료! 결과 미리보기:")
        st.dataframe(result, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            result.to_excel(writer, index=False)
        output.seek(0)

        st.download_button(
            label="📥 결과 다운로드 (.xlsx)",
            data=output,
            file_name="matched_result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
