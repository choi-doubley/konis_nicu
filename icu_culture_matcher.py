import pandas as pd
import streamlit as st
from datetime import datetime
import io

# 날짜 자동 인식
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

# 자동 컬럼 탐색
def find_column(candidates, columns):
    for candidate in candidates:
        for col in columns:
            if candidate.lower().replace(" ", "") in col.lower().replace(" ", ""):
                return col
    return None

# Streamlit 시작
st.set_page_config(page_title="NICU KONIS Matcher", layout="centered")
st.markdown("<h1 style='text-align:center;'>NICU KONIS<br>혈액배양양성환자 작성 도우미</h1>", unsafe_allow_html=True)

# 파일 업로드
icu_file = st.file_uploader("📄 중환자실 입퇴실 파일 업로드 (.xlsx)", type=["xlsx"])
culture_file = st.file_uploader("📄 혈액배양 양성 파일 업로드 (.xlsx)", type=["xlsx"])

if icu_file and culture_file:
    icu_df = pd.read_excel(icu_file)
    culture_df = pd.read_excel(culture_file)

    st.subheader("📁 중환자실 입퇴실 파일의 컬럼 선택")

    icu_id = st.selectbox(
        "🆔 환자 ID 컬럼", icu_df.columns,
        index=icu_df.columns.get_loc(
            find_column(["환자번호", "병록번호", "patientid", "patient_id"], icu_df.columns) or icu_df.columns[0]
        )
    )
    icu_in = st.selectbox(
        "📅 입실일 컬럼", icu_df.columns,
        index=icu_df.columns.get_loc(
            find_column(["입실일", "입원일", "admit", "입실", "admission"], icu_df.columns) or icu_df.columns[0]
        )
    )
    icu_out = st.selectbox(
        "📅 퇴실일 컬럼", icu_df.columns,
        index=icu_df.columns.get_loc(
            find_column(["퇴실일", "퇴원일", "discharge", "퇴실", "퇴원"], icu_df.columns) or icu_df.columns[0]
        )
    )

    st.subheader("🧫 혈액배양 양성 파일의 컬럼 선택")

    culture_id = st.selectbox(
        "🆔 환자 ID 컬럼", culture_df.columns,
        index=culture_df.columns.get_loc(
            find_column(["환자번호", "병록번호", "patientid", "patient_id"], culture_df.columns) or culture_df.columns[0]
        )
    )
    culture_date = st.selectbox(
        "📅 혈액배양일 컬럼", culture_df.columns,
        index=culture_df.columns.get_loc(
            find_column(["배양일", "채취일", "검사일", "culturedate", "검체일", "채혈일"], culture_df.columns) or culture_df.columns[0]
        )
    )

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

        # 날짜 단위 비교
        merged['culture_date_day'] = merged[culture_date].dt.date
        merged['icu_in_day'] = merged[icu_in].dt.date
        merged['icu_out_day'] = merged[icu_out].dt.date

        # 캘린더 데이 기준 범위
        merged['icu_day_start'] = merged['icu_in_day'] + pd.Timedelta(days=2)
        merged['icu_day_end'] = merged['icu_out_day'] + pd.Timedelta(days=1)

        # 조건 필터링
        matched = merged[
            (merged['culture_date_day'] >= merged['icu_day_start']) &
            (merged['culture_date_day'] <= merged['icu_day_end'])
        ]

        # 최종 병합 (left join 유지)
        result = culture_df.merge(
            matched[[culture_id, culture_date, icu_in, icu_out]],
            on=[culture_id, culture_date],
            how='left'
        )

        # 정렬: ICU 입실일 존재 → culture_date 순
        result_sorted = result.sort_values(
            by=[icu_in, culture_date],
            ascending=[True, True],
            na_position="last"
        )

        # 결과 출력 및 다운로드
        st.success("✅ 매칭 완료! 결과 미리보기 (정렬됨):")
        st.dataframe(result_sorted, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            result_sorted.to_excel(writer, index=False)
        output.seek(0)

        st.download_button(
            label="📥 결과 다운로드 (.xlsx)",
            data=output,
            file_name="matched_result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
