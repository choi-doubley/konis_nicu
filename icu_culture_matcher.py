import pandas as pd
import streamlit as st
from datetime import datetime
import io
from collections import Counter

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

# 구분자 자동 감지
def detect_delimiter(series):
    sample_values = series.dropna().astype(str).head(100)
    delimiters = ['/', '-', '|', ',', ' ']
    counts = Counter()
    for val in sample_values:
        for delim in delimiters:
            if delim in val:
                counts[delim] += 1
    return counts.most_common(1)[0][0] if counts else '/'

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

    # 병합에 사용할 전체 후보 파일
    all_column_sources = {
        "중환자실 파일": icu_df,
        "혈액배양 파일": culture_df
    }
    if not info_df.empty:
        all_column_sources["추가정보 파일"] = info_df

    all_column_options = list(all_column_sources.keys())

    st.markdown("---")
    st.markdown("### 📅 생년월일 정보")
    birth_unavailable = st.checkbox("❔ 생년월일 정보가 없습니다 (비워둡니다)", value=False)
    if not birth_unavailable:
        birth_source = st.selectbox("📁 생년월일이 있는 파일", all_column_options, key="birth_src")
        birth_df = all_column_sources[birth_source]
        birth_id_col = st.selectbox("🔑 환자 ID 컬럼", birth_df.columns, key="birth_id", index=birth_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], birth_df.columns) or birth_df.columns[0]))
        birth_col = st.selectbox("📅 생년월일 컬럼", birth_df.columns, key="birth_col", index=birth_df.columns.get_loc(find_column(["생년월일", "birthdate", "dob"], birth_df.columns) or birth_df.columns[0]))

    st.markdown("---")
    st.markdown("### 👶 이름 정보")
    name_source = st.selectbox("📁 이름이 있는 파일", all_column_options, key="name_src")
    name_df = all_column_sources[name_source]
    name_id_col = st.selectbox("🔑 환자 ID 컬럼", name_df.columns, key="name_id", index=name_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], name_df.columns) or name_df.columns[0]))
    name_col = st.selectbox("🧒 이름 컬럼", name_df.columns, key="name_col", index=name_df.columns.get_loc(find_column(["이름", "성명", "name"], name_df.columns) or name_df.columns[0]))

    st.markdown("---")
    st.markdown("### ⚧️ 성별 정보")
    gender_source = st.selectbox("📁 성별이 있는 파일", all_column_options, key="gender_src")
    gender_df = all_column_sources[gender_source]
    gender_id_col = st.selectbox("🔑 환자 ID 컬럼", gender_df.columns, key="gender_id", index=gender_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], gender_df.columns) or gender_df.columns[0]))

    use_combined = st.checkbox("성별이 다른 정보(예: 나이)와 하나의 컬럼에 함께 있음")
    if use_combined:
        combined_col = st.selectbox("📑 결합된 컬럼명", gender_df.columns, key="combined_col", index=gender_df.columns.get_loc(find_column(["성별/나이", "S/A", "S|A"], gender_df.columns) or gender_df.columns[0]))
        detected_delim = detect_delimiter(gender_df[combined_col])
        delimiter = st.text_input("🔹 구분자 (예: /)", value=detected_delim)
        position = st.radio("🔹 성별은 구분자를 기준으로 어디에 있나요?", ["앞", "뒤"], horizontal=True)
    else:
        gender_col = st.selectbox("성별 컬럼", gender_df.columns, key="gender_col", index=gender_df.columns.get_loc(find_column(["성별", "gender", "sex"], gender_df.columns) or gender_df.columns[0]))
