import pandas as pd
import streamlit as st
from datetime import datetime
import io
from collections import Counter

# 날짜 자동 인식
# ... (생략된 유틸 함수들 포함)

# 생략 없이 전체 로직 이어서 작성

st.markdown("---")
    st.markdown("### 👶 이름 정보")
    name_source = st.selectbox("📁 이름이 있는 파일", all_column_options, key="name_src")
    name_df = all_column_sources[name_source]
    name_col = st.selectbox("컬럼명", name_df.columns, key="name_col", index=name_df.columns.get_loc(find_column(["이름", "성명", "name"], name_df.columns) or name_df.columns[0]))
    name_id_col = st.selectbox("ID 컬럼명", name_df.columns, key="name_id", index=name_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], name_df.columns) or name_df.columns[0]))

    st.markdown("---")
    st.markdown("### ⚧️ 성별 정보")
    gender_source = st.selectbox("📁 성별이 있는 파일", all_column_options, key="gender_src")
    gender_df = all_column_sources[gender_source]
    gender_id_col = st.selectbox("ID 컬럼명", gender_df.columns, key="gender_id", index=gender_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], gender_df.columns) or gender_df.columns[0]))

    use_combined = st.checkbox("성별이 다른 정보(예: 나이)와 하나의 컬럼에 함께 있음")
    if use_combined:
        combined_col = st.selectbox("📑 결합된 컬럼명", gender_df.columns, key="combined_col", index=gender_df.columns.get_loc(find_column(["성별/나이", "성별|나이", "S/A", "S|A"], gender_df.columns) or gender_df.columns[0]))
        detected_delim = detect_delimiter(gender_df[combined_col])
        delimiter = st.text_input("🔹 구분자 (예: /)", value=detected_delim)
        position = st.radio("🔹 성별은 구분자를 기준으로 어디에 있나요?", ["앞", "뒤"], horizontal=True)
    else:
        gender_col = st.selectbox("컬럼명", gender_df.columns, key="gender_col", index=gender_df.columns.get_loc(find_column(["성별", "gender", "sex"], gender_df.columns) or gender_df.columns[0]))

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

        name_df = name_df[[name_id_col, name_col]].copy()
        name_df['초성'] = name_df[name_col].apply(get_initials)
        result = result.merge(name_df[[name_id_col, '초성']], left_on=culture_id, right_on=name_id_col, how='left')

        if not birth_available:
            birth_df = birth_df[[birth_id_col, birth_col]].copy()
            result = result.merge(birth_df, left_on=culture_id, right_on=birth_id_col, how='left')

        if use_combined:
            comb_df = gender_df[[gender_id_col, combined_col]].copy()
            if position == "앞":
                comb_df['성별'] = comb_df[combined_col].str.split(delimiter).str[0]
            else:
                comb_df['성별'] = comb_df[combined_col].str.split(delimiter).str[-1]
            result = result.merge(comb_df[[gender_id_col, '성별']], left_on=culture_id, right_on=gender_id_col, how='left')
        else:
            gender_df = gender_df[[gender_id_col, gender_col]].copy()
            gender_df = gender_df.rename(columns={gender_col: '성별'})
            result = result.merge(gender_df, left_on=culture_id, right_on=gender_id_col, how='left')

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
