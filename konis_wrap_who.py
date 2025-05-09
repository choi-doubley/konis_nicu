## py -m streamlit run konis_wrap_who_streamlit.py

import pandas as pd
import io
from datetime import datetime, timedelta
import re
from collections import Counter
import streamlit as st

# 자동 컬럼 탐색
def find_column(candidates, columns):
    for candidate in candidates:
        for col in columns:
            if candidate.lower().replace(" ", "") in col.lower().replace(" ", ""):
                return col
    return None

# 날짜 포맷 보정
def fix_time_format(val):
    val_str = str(val)
    match = re.match(r'(.*\s)(\d{2}):?(\d{2})(\d{2})$', val_str)
    if match:
        return f"{match.group(1)}{match.group(2)}:{match.group(3)}:{match.group(4)}"
    match2 = re.match(r'(\d{2})(\d{2})(\d{2})$', val_str)
    if match2:
        return f"{match2.group(1)}:{match2.group(2)}:{match2.group(3)}"
    return val_str

# 날짜 파싱 함수
def parse_dates_safe(series):
    known_formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y",
        "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d %H%M",
        "%Y/%m/%d %H%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"
    ]
    def try_parse(val):
        if pd.isna(val): return pd.NaT
        val = fix_time_format(val)
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

# Streamlit 앱 시작
st.set_page_config(page_title="환자 ID 추정기", layout="centered")
st.title("🔍 환자 ID 추정기")

st.markdown("<h1 style='text-align:center;'>👶 NICU KONIS<br>타당도 조사 도우미2</h1><br>"
            "<h3 style='text-align:center;'>감염환자 기록지 ID 찾기</h3>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:right; font-size: 0.9em; color: gray;'>"
    "<a href='https://github.com/choi-doubley/konis_nicu/blob/main/KONIS_NICU_streamlit_manual2.pdf?raw=T' target='_blank'>매뉴얼 다운로드</a><br>"
    "최종 업데이트: 2025-05-08<br>" 
    "문의: cyypedr@gmail.com"
    "</div>",
    unsafe_allow_html=True
)

file1 = st.file_uploader("🚨 KONIS WRAP 등록환자 파일", type=["xlsx", "csv"])
file2 = st.file_uploader("👶 중환자실 입퇴실 파일", type=["xlsx", "csv"])
file3 = st.file_uploader("🧫 혈액배양 파일", type=["xlsx", "csv"])

if file1 and file2 and file3:
    df1 = pd.read_excel(file1, dtype=str) if file1.name.endswith("xlsx") else pd.read_csv(file1, dtype=str)
    df2 = pd.read_excel(file2, dtype=str) if file2.name.endswith("xlsx") else pd.read_csv(file2, dtype=str)
    df3 = pd.read_excel(file3, dtype=str) if file3.name.endswith("xlsx") else pd.read_csv(file3, dtype=str)

    st.subheader("🚨 KONIS WRAP 등록환자 파일 컬럼 선택")
    caseno = st.selectbox("증례코드", df1.columns,
                          index=df1.columns.get_loc(find_column(["증례코드"], df1.columns) or df1.columns[1]))
    dob1 = st.selectbox("📅 생년월일", df1.columns, index=df1.columns.get_loc(find_column(["생년월일", "birthdate", "dob"], df1.columns) or df1.columns[0]))
    gender1 = st.selectbox("👦👧 성별", df1.columns,
                           index=df1.columns.get_loc(find_column(["성별", "gender", "sex"], df1.columns) or df1.columns[0]))
    date_icu1 = st.selectbox("📅 중환자실 입원일", df1.columns,
                             index=df1.columns.get_loc(find_column(["중환자실입원일", "admission", "입원"], df1.columns) or df1.columns[6]))
    date_infection = st.selectbox("🌡️ 감염발생일", df1.columns,
                                  index=df1.columns.get_loc(find_column(["감염발생일", "감염"], df1.columns) or df1.columns[10]))

    st.subheader("👶 중환자실 입퇴실 파일 컬럼 선택")
    id2 = st.selectbox("🆔 환자ID", df2.columns,
                       index=df2.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], df2.columns) or df2.columns[0]))
    date_icu2 = st.selectbox("📅 중환자실 입원일", df2.columns,
                             index=df2.columns.get_loc(find_column(["입실"], df2.columns) or df2.columns[0]))
    date_icu2_out = st.selectbox("📅 중환자실 퇴원일", df2.columns,
                                 index=df2.columns.get_loc(find_column(["퇴실"], df2.columns) or df2.columns[0]))

    st.subheader("🧫 혈액배양 파일 컬럼 선택")
    id3 = st.selectbox("🆔 환자ID", df3.columns,
                       index=df3.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], df3.columns) or df3.columns[0]))
    date_culture = st.selectbox("📅 혈액배양 시행일", df3.columns,
                                index=df3.columns.get_loc(find_column(["시행일", "채취일", "검사일", "접수일"], df3.columns) or df3.columns[0]))
    result_culture = st.selectbox("🦠 혈액배양 결과(분리균)", df3.columns,
                                  index=df3.columns.get_loc(find_column(["미생물", "결과"], df3.columns) or df3.columns[0]))

        # 병합에 사용할 전체 후보 파일
    all_column_sources = {
        "중환자실 파일": df2,
        "혈액배양 파일": df3
    }

    all_column_options = ["중환자실 파일"] + [k for k in all_column_sources.keys() if k != "중환자실 파일"]

    st.markdown("---")
    st.markdown("📅 생년월일 정보")
    birth_source = st.selectbox("📁 생년월일이 있는 파일", all_column_options, key="birth_src", index=0)
    birth_df = all_column_sources[birth_source]
    birth_id_col = st.selectbox("🆔 환자 ID 컬럼", birth_df.columns, key="birth_id", index=birth_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], birth_df.columns) or birth_df.columns[0]))
    birth_col = st.selectbox("📅 생년월일 컬럼", birth_df.columns, key="birth_col", index=birth_df.columns.get_loc(find_column(["생년월일", "birthdate", "dob"], birth_df.columns) or birth_df.columns[0]))

    st.markdown("---")
    st.markdown("### 👦👧 성별 정보")
    gender_source = st.selectbox("📁 성별이 있는 파일", all_column_options, key="gender_src", index=0)
    gender_df = all_column_sources[gender_source]
    gender_id_col = st.selectbox("🆔 환자 ID 컬럼", gender_df.columns, key="gender_id", index=gender_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], gender_df.columns) or gender_df.columns[0]))

    gender_combined = st.checkbox("성별이 다른 정보(예: 나이)와 하나의 컬럼에 함께 있음")
    if gender_combined:
        combined_col = st.selectbox("📑 결합된 컬럼명", gender_df.columns, key="combined_col", index=gender_df.columns.get_loc(find_column(["성별/나이", "S/A", "S|A"], gender_df.columns) or gender_df.columns[0]))
        detected_delim = detect_delimiter(gender_df[combined_col])
        delimiter = st.text_input("🔹 구분자 (예: /)", value=detected_delim)
        position = st.radio("🔹 성별은 구분자를 기준으로 어디에 있나요?", ["앞", "뒤"], horizontal=True)
    else:
        gender_col = st.selectbox("성별 컬럼", gender_df.columns, key="gender_col", index=gender_df.columns.get_loc(find_column(["성별", "gender", "sex"], gender_df.columns) or gender_df.columns[0]))

    if st.button("🚀 ID 추정 실행"):
        if gender_combined:
            comb_df = gender_df[[gender_id_col, combined_col]].copy()
            comb_df = comb_df.drop_duplicates(subset=[gender_id_col])
            if position == "앞":
                comb_df['gender'] = comb_df[combined_col].str.split(delimiter).str[0]
            else:
                comb_df['gender'] = comb_df[combined_col].str.split(delimiter).str[-1]
            gender_df = comb_df[[gender_id_col,'gender']]
        else:
            gender_df = gender_df.drop_duplicates(subset=[gender_id_col])
            gender_df = gender_df[[gender_id_col, gender_col]].rename(columns={gender_col: 'gender'})
    
        # df 정리
        columns_to_use = [caseno, dob1, gender1, date_icu1, date_infection]
        optional_cols = ['재태연령(주)', '재태연령(일)', '출생체중', 'LCBI종류', '병원체명1', '병원체명2']
        columns_to_use += [col for col in optional_cols if col in df1.columns]
        df1 = df1[columns_to_use]
        df2 = df2[[id2, date_icu2, date_icu2_out]] ## ICU
        df3 = df3[[id3, date_culture, result_culture]] ## culture
        birth_df = birth_df.drop_duplicates(subset=[birth_id_col])
        birth_df = birth_df[[birth_id_col, birth_col]]
        gender_df = gender_df[[gender_id_col, 'gender']]

        # 날짜 변환
        for col in [dob1, date_icu1, date_infection]:
            df1[col] = parse_dates_safe(df1[col]).dt.date
        for col in [date_icu2, date_icu2_out]:
            df2[col] = parse_dates_safe(df2[col]).dt.date
        df3[date_culture] = parse_dates_safe(df3[date_culture]).dt.date
        birth_df[birth_col] = parse_dates_safe(birth_df[birth_col]).dt.date

        # 병합
        merged = pd.merge(df3, df2, left_on=id3, right_on=id2, how='inner')
        
        # 날짜 계산      
        merged['culture_date_day'] = merged[date_culture].copy()
        merged['icu_in_day'] = merged[date_icu2].copy()
        merged['icu_out_day'] = merged[date_icu2_out].copy()
        merged['icu_day_start'] = merged['icu_in_day'] + timedelta(days=2)
        merged['icu_day_end'] = merged['icu_out_day'] + timedelta(days=1)
        merged = merged.drop_duplicates(subset=[id3, 'culture_date_day', 'icu_in_day'])

        # 감시기간 포함 조건
        condition_matched = (
            (merged['icu_day_start'].notna()) &
            (merged['culture_date_day'] >= merged['icu_day_start']) &
            (
                (merged['culture_date_day'] <= merged['icu_day_end']) |
                (merged['icu_day_end'].isna())
            )
        )
        merged2 = merged.loc[condition_matched].copy()
        merged3 = pd.merge(merged2, birth_df, left_on=id3, right_on=birth_id_col, how='left')
        merged3 = pd.merge(merged3, gender_df, left_on=id3, right_on=gender_id_col, how='left')


        # 성별, 생년월일 기준 병합
        result = []
        for i, row in df1.iterrows():
            g, dob, icu_d, inf_d, case_id = row[gender1], row[dob1], row[date_icu1], row[date_infection], row[caseno]
            candidates = merged3[
                (merged3['gender'] == g) &
                (merged3[birth_col] == dob) &
                (merged3['icu_in_day'] == icu_d) &
                (merged3['culture_date_day'] >= inf_d) &
                (merged3['culture_date_day'] <= inf_d + timedelta(days=2))
            ]
            top_candidates = candidates[[id3, result_culture]].drop_duplicates().head(3)
            if not top_candidates.empty:
                for _, cand in top_candidates.iterrows():
                    result.append({
                        caseno: case_id,
                        "추정ID": cand[id3],
                        "추정ID분리균": cand[result_culture]
                    })
            else:
                result.append({
                    caseno: case_id,
                    "추정ID": "",
                    "추정ID분리균": ""
                })

        result_df = pd.DataFrame(result)
        sub_cols = [col for col in df1.columns if col != caseno]
        final = pd.merge(df1[[caseno] + sub_cols], result_df, on=caseno, how='right').drop_duplicates()

        # final = final[["추정ID후보"] + [col for col in final.columns if col != "추정ID후보"]]

        st.success("✅ 추정 완료!")
        st.dataframe(final, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            final.to_excel(writer, index=False)
        output.seek(0)
        st.download_button("📥 결과 다운로드 (.xlsx)", data=output,
                           file_name="NICU_감염환자자료_ids.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
