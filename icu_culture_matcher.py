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

# 초성 추출 함수
def get_initials(hangul_string):
    CHOSUNG_LIST = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ',
                    'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ',
                    'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    initials = ''
    for char in str(hangul_string):
        if '가' <= char <= '힣':
            char_code = ord(char) - ord('가')
            cho = char_code // (21 * 28)
            initials += CHOSUNG_LIST[cho]
        else:
            initials += char
    return initials

# 자동 컬럼 탐색
def find_column(candidates, columns):
    for candidate in candidates:
        for col in columns:
            if candidate.lower().replace(" ", "") in col.lower().replace(" ", ""):
                return col
    return None

# Streamlit 시작
st.set_page_config(page_title="NICU KONIS Matcher", layout="centered")
st.markdown("<h1 style='text-align:center;'>👶 NICU KONIS<br>혈액배양양성환자 작성 도우미</h1>", unsafe_allow_html=True)

# 파일 업로드
icu_file = st.file_uploader("📄 중환자실 입퇴실 파일", type=["xlsx"])
culture_file = st.file_uploader("🧫 혈액배양 파일", type=["xlsx"])
info_file = st.file_uploader("🔖 추가 환자정보 파일 (optional)", type=["xlsx"])

if icu_file and culture_file:
    icu_df = pd.read_excel(icu_file)
    culture_df = pd.read_excel(culture_file)
    info_df = pd.read_excel(info_file) if info_file else pd.DataFrame()

    st.subheader("🏥 중환자실 파일 컬럼 선택")
    icu_id = st.selectbox("🔑 환자 ID", icu_df.columns)
    icu_in = st.selectbox("📅 입실일", icu_df.columns)
    icu_out = st.selectbox("📅 퇴실일", icu_df.columns)

    st.subheader("🧫 혈액배양 파일 컬럼 선택")
    culture_id = st.selectbox("🔑 환자 ID", culture_df.columns)
    culture_date = st.selectbox("📅 혈액배양일", culture_df.columns)

    # 병합 대상 컬럼 선택을 위한 전체 column pool 구성
    all_column_sources = {
        "중환자실 파일": icu_df,
        "혈액배양 파일": culture_df
    }
    if not info_df.empty:
        all_column_sources["추가정보 파일"] = info_df

    all_column_options = list(all_column_sources.keys())

    st.subheader("🔔 환자 정보 (생년월일/이름/성별/나이)")
    birth_source = st.selectbox("📁 생년월일이 있는 파일", all_column_options)
    birth_col = st.selectbox("📅 생년월일 컬럼", all_column_sources[birth_source].columns)

    name_source = st.selectbox("📁 이름이 있는 파일", all_column_options)
    name_col = st.selectbox("👶 환자이름 컬럼", all_column_sources[name_source].columns)

    use_combined = st.checkbox("합성 (성별/나이) 하나의 컬럼에 있음")
    if use_combined:
        combined_source = st.selectbox("📁 합성 컬럼이 있는 파일", all_column_options)
        combined_col = st.selectbox("합성 컬럼", all_column_sources[combined_source].columns)
        delimiter = st.text_input("구분자 (default: /)", value="/")
    else:
        gender_source = st.selectbox("📁 성별이 있는 파일", all_column_options)
        gender_col = st.selectbox("♂️ 성별 컬럼", all_column_sources[gender_source].columns)
        age_source = st.selectbox("📁 나이가 있는 파일", all_column_options)
        age_col = st.selectbox("👶 나이 컬럼", all_column_sources[age_source].columns)

    if st.button("🔁 매칭 실행"):
        icu_df[icu_in] = parse_dates_safe(icu_df[icu_in])
        icu_df[icu_out] = parse_dates_safe(icu_df[icu_out])
        culture_df[culture_date] = parse_dates_safe(culture_df[culture_date])

        merged = culture_df.merge(
            icu_df[[icu_id, icu_in, icu_out]],
            left_on=culture_id, right_on=icu_id, how='left')

        merged['culture_date_day'] = merged[culture_date].dt.date
        merged['icu_in_day'] = merged[icu_in].dt.date
        merged['icu_out_day'] = merged[icu_out].dt.date
        merged['icu_day_start'] = merged['icu_in_day'] + pd.Timedelta(days=2)
        merged['icu_day_end'] = merged['icu_out_day'] + pd.Timedelta(days=1)

        matched = merged[(merged['culture_date_day'] >= merged['icu_day_start']) &
                         (merged['culture_date_day'] <= merged['icu_day_end'])]

        result = culture_df.merge(
            matched[[culture_id, culture_date, icu_in, icu_out]],
            on=[culture_id, culture_date], how='left')

        # 이름/생년월일/성별/나이 붙이기
        name_df = all_column_sources[name_source][[name_col, icu_id]].copy()
        name_df['초성'] = name_df[name_col].apply(get_initials)
        result = result.merge(name_df, left_on=culture_id, right_on=icu_id, how='left')

        birth_df = all_column_sources[birth_source][[birth_col, icu_id]]
        result = result.merge(birth_df, left_on=culture_id, right_on=icu_id, how='left')

        if use_combined:
            comb_df = all_column_sources[combined_source][[combined_col, icu_id]].copy()
            comb_df[['성별', '나이']] = comb_df[combined_col].str.split(delimiter, expand=True)
            result = result.merge(comb_df[['성별', '나이', icu_id]], left_on=culture_id, right_on=icu_id, how='left')
        else:
            gender_df = all_column_sources[gender_source][[gender_col, icu_id]].copy()
            gender_df = gender_df.rename(columns={gender_col: '성별'})
            age_df = all_column_sources[age_source][[age_col, icu_id]].copy()
            age_df = age_df.rename(columns={age_col: '나이'})
            result = result.merge(gender_df, left_on=culture_id, right_on=icu_id, how='left')
            result = result.merge(age_df, left_on=culture_id, right_on=icu_id, how='left')

        result_sorted = result.sort_values(by=[icu_in, culture_date], ascending=[True, True], na_position="last")

        st.success("✅ 매칭 완료! 결과 미리보기")
        st.dataframe(result_sorted, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            result_sorted.to_excel(writer, index=False)
        output.seek(0)

        st.download_button("📥 결과 다운로드 (.xlsx)", data=output,
                           file_name="matched_result.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
