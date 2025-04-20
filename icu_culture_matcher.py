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
st.markdown(
"<div style='text-align:right; font-size: 0.9em; color: gray;'>"
"최종 업데이트: 2025-04-19<br> 문의: cyypedr@gmail.com"
"</div>", unsafe_allow_html=True)


# 파일 업로드
icu_file = st.file_uploader("👶 중환자실 입퇴실 파일", type=["xlsx"])
culture_file = st.file_uploader("🧫 혈액배양 파일", type=["xlsx"])
bsi_file = st.file_uploader("🚨 BSI 환자목록 파일 (optional)", type=["xlsx"])
info_file = st.file_uploader("📄 추가 환자정보 파일 (optional)", type=["xlsx"])

if icu_file and culture_file:
    icu_df = pd.read_excel(icu_file)
    culture_df = pd.read_excel(culture_file)
    bsi_df = pd.read_excel(bsi_file) if bsi_file else pd.DataFrame()
    info_df = pd.read_excel(info_file) if info_file else pd.DataFrame()

    st.subheader("🧸 중환자실 파일 컬럼 선택")
    icu_id = st.selectbox("🆔 환자 ID 컬럼", icu_df.columns, index=icu_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], icu_df.columns) or icu_df.columns[0]))
    icu_in = st.selectbox("📅 입실일", icu_df.columns, index=icu_df.columns.get_loc(find_column(["입실"], icu_df.columns) or icu_df.columns[0]))
    icu_out = st.selectbox("📅 퇴실일", icu_df.columns, index=icu_df.columns.get_loc(find_column(["퇴실"], icu_df.columns) or icu_df.columns[0]))

    st.subheader("🧫 혈액배양 파일 컬럼 선택")
    culture_id = st.selectbox("🆔 환자 ID", culture_df.columns, index=culture_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], culture_df.columns) or culture_df.columns[0]))
    culture_date = st.selectbox("📅 혈액배양일", culture_df.columns, index=culture_df.columns.get_loc(find_column(["시행일", "채취일", "검사일"], culture_df.columns) or culture_df.columns[0]))
    use_result_col = st.checkbox("❔ 분리균 정보가 없습니다", value=False)
    use_result_col = not use_result_col
    if use_result_col:
        culture_result = st.selectbox("🦠 혈액배양 결과(분리균) 컬럼", culture_df.columns, index=culture_df.columns.get_loc(find_column(["균"], culture_df.columns) or culture_df.columns[0]))

if not bsi_df.empty:
    st.subheader("🚨 BSI 여부 파일 컬럼 선택")
    bsi_id_col = st.selectbox("🆔 환자 ID", bsi_df.columns,
        index=bsi_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], bsi_df.columns) or bsi_df.columns[0])
    )

    # 병합에 사용할 전체 후보 파일
    all_column_sources = {
        "중환자실 파일": icu_df,
        "혈액배양 파일": culture_df
    }

    if not bsi_df.empty:
        all_column_sources["BSI 파일"] = bsi_df
    
    if not info_df.empty:
        all_column_sources["추가정보 파일"] = info_df

    all_column_options = list(all_column_sources.keys())

    st.markdown("---")
    st.markdown("### 📅 생년월일 정보")
    birth_unavailable = st.checkbox("❔ 생년월일 정보가 없습니다", value=False)
    if not birth_unavailable:
        birth_source = st.selectbox("📁 생년월일이 있는 파일", all_column_options, key="birth_src")
        birth_df = all_column_sources[birth_source]
        birth_id_col = st.selectbox("🆔 환자 ID 컬럼", birth_df.columns, key="birth_id", index=birth_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], birth_df.columns) or birth_df.columns[0]))
        birth_col = st.selectbox("📅 생년월일 컬럼", birth_df.columns, key="birth_col", index=birth_df.columns.get_loc(find_column(["생년월일", "birthdate", "dob"], birth_df.columns) or birth_df.columns[0]))

    st.markdown("---")
    st.markdown("### 👶 이름 정보")
    name_source = st.selectbox("📁 이름이 있는 파일", all_column_options, key="name_src")
    name_df = all_column_sources[name_source]
    name_id_col = st.selectbox("🔑 환자 ID 컬럼", name_df.columns, key="name_id", index=name_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], name_df.columns) or name_df.columns[0]))
    name_col = st.selectbox("🧒 이름 컬럼", name_df.columns, key="name_col", index=name_df.columns.get_loc(find_column(["환자명","이름", "성명", "name"], name_df.columns) or name_df.columns[0]))

    st.markdown("---")
    st.markdown("### 👦👧 성별 정보")
    gender_source = st.selectbox("📁 성별이 있는 파일", all_column_options, key="gender_src")
    gender_df = all_column_sources[gender_source]
    gender_id_col = st.selectbox("🆔 환자 ID 컬럼", gender_df.columns, key="gender_id", index=gender_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], gender_df.columns) or gender_df.columns[0]))

    use_combined = st.checkbox("성별이 다른 정보(예: 나이)와 하나의 컬럼에 함께 있음")
    if use_combined:
        combined_col = st.selectbox("📑 결합된 컬럼명", gender_df.columns, key="combined_col", index=gender_df.columns.get_loc(find_column(["성별/나이", "S/A", "S|A"], gender_df.columns) or gender_df.columns[0]))
        detected_delim = detect_delimiter(gender_df[combined_col])
        delimiter = st.text_input("🔹 구분자 (예: /)", value=detected_delim)
        position = st.radio("🔹 성별은 구분자를 기준으로 어디에 있나요?", ["앞", "뒤"], horizontal=True)
    else:
        gender_col = st.selectbox("성별 컬럼", gender_df.columns, key="gender_col", index=gender_df.columns.get_loc(find_column(["성별", "gender", "sex"], gender_df.columns) or gender_df.columns[0]))

    if st.button("🔁 매칭 실행"):
        # 날짜 처리
        icu_df[icu_in] = parse_dates_safe(icu_df[icu_in])
        icu_df[icu_out] = parse_dates_safe(icu_df[icu_out])
        culture_df[culture_date] = parse_dates_safe(culture_df[culture_date])

        # ICU 데이터 병합
        merged = culture_df.merge(
            icu_df[[icu_id, icu_in, icu_out]],
            left_on=culture_id, right_on=icu_id, how='left'
        )

        # 캘린더 데이 범위 계산
        merged['culture_date_day'] = merged[culture_date].dt.date
        merged['icu_in_day'] = merged[icu_in].dt.date
        merged['icu_out_day'] = merged[icu_out].dt.date
        merged['icu_day_start'] = merged['icu_in_day'] + pd.Timedelta(days=2)
        merged['icu_day_end'] = merged['icu_out_day'] + pd.Timedelta(days=1)

        # 조건에 맞는 환자만 필터링
        matched = merged[
            (merged['culture_date_day'] >= merged['icu_day_start']) &
            (merged['culture_date_day'] <= merged['icu_day_end'])
        ]

        # culture_df와 다시 병합하여 원본 유지
        result = culture_df.merge(
            matched[[culture_id, culture_date, icu_in, icu_out]],
            on=[culture_id, culture_date], how='left'
        )

        # 이름 초성 변환 병합
        name_df = name_df[[name_id_col, name_col]].copy()
        name_df['이름'] = name_df[name_col].apply(get_initials)
        result = result.merge(name_df[[name_id_col, '이름']], left_on=culture_id, right_on=name_id_col, how='left')

        # 성별 병합
        if use_combined:
            comb_df = gender_df[[gender_id_col, combined_col]].copy()
            if position == "앞":
                comb_df['성별'] = comb_df[combined_col].str.split(delimiter).str[0]
            else:
                comb_df['성별'] = comb_df[combined_col].str.split(delimiter).str[-1]
            result = result.merge(comb_df[[gender_id_col, '성별']], left_on=culture_id, right_on=gender_id_col, how='left')
        else:
            gender_df = gender_df[[gender_id_col, gender_col]].rename(columns={gender_col: '성별'})
            result = result.merge(gender_df, left_on=culture_id, right_on=gender_id_col, how='left')

        # 생년월일 병합 (선택적)
        birth_column_success = False ## 기본값 설정
        if not birth_unavailable:
            try:
                birth_df = birth_df[[birth_id_col, birth_col]].copy()

                # 문자열 길이 기준 필터 (길이 8 이상이 50% 이상이어야 함)
                str_lengths = birth_df[birth_col].astype(str).str.len()
                long_enough_ratio = (str_lengths >= 8).mean()

                if long_enough_ratio < 0.5:
                    st.warning("❌ 선택한 생년월일 컬럼의 값 대부분이 날짜 형식이 아닙니다. 컬럼 선택을 다시 확인해 주세요.")
                else:
                    # 날짜로 파싱 시도
                    parsed_birth = parse_dates_safe(birth_df[birth_col])
                    valid_ratio = parsed_birth.notna().mean()

                    if valid_ratio < 0.5:
                        st.warning("⚠️ 생년월일 컬럼의 값 중 다수가 날짜로 변환되지 않았습니다. 일부 정보가 누락되었을 수 있습니다.")
                    else:
                        birth_df[birth_col] = parsed_birth
                        st.info("📅 생년월일 컬럼이 문자열 형식으로 되어 있어 자동으로 날짜로 변환했습니다.")
                        result = result.merge(birth_df, left_on=culture_id, right_on=birth_id_col, how='left')
                        result.rename(columns={birth_col: "생년월일"}, inplace=True)
                        birth_column_success = "생년월일" in result.columns

            except Exception as e:
                st.warning(f"⚠️ 생년월일 병합에 실패했습니다: {e}")

        # 컬럼명 정리
        result.rename(columns={
            culture_id: "환자ID",
            icu_in: "입실일",
            icu_out: "퇴실일",
            culture_date: "혈액배양일"
        }, inplace=True)
        
        if use_result_col:
            result.rename(columns={culture_result: "분리균"}, inplace=True)


        # 정렬 및 일련번호
        result_sorted = result.sort_values(by=["입실일", "혈액배양일"], ascending=[True, True], na_position="last")
        result_sorted.insert(0, "No", range(1, len(result_sorted) + 1))

        # BSI 여부 병합
        if not bsi_df.empty:
            result_sorted["BSI"] = result_sorted["환자ID"].isin(bsi_df[bsi_id_col]).map({True: "Y", False: None})
    
        # 환자ID를 문자열로 강제 변환
        result_sorted["환자ID"] = result_sorted["환자ID"].astype(str)

        # 날짜 포맷을 yyyy-mm-dd로 통일
        for col in ["입실일", "퇴실일", "혈액배양일", "생년월일"]:
            if col in result_sorted.columns:
                result_sorted[col] = pd.to_datetime(result_sorted[col], errors="coerce").dt.strftime("%Y-%m-%d")

        
        # 선택 컬럼 출력
        columns_to_show = ["No", "환자ID", "이름", "성별"]
        if birth_column_success:
            columns_to_show.append("생년월일")
        columns_to_show += ["입실일", "퇴실일", "혈액배양일"]
        if use_result_col:
            columns_to_show.append("분리균")
        if not bsi_df.empty:
            columns_to_show.append("BSI")

        st.success("✅ 매칭 완료! 결과 미리보기")
        st.dataframe(result_sorted[columns_to_show], use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            result_sorted[columns_to_show] = result_sorted[columns_to_show].astype({"환자ID": str})
            result_sorted[columns_to_show].to_excel(writer, index=False)
        output.seek(0)

        st.download_button("📥 결과 다운로드 (.xlsx)", data=output,
                           file_name="matched_result.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
