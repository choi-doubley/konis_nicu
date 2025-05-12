## py -m streamlit run icu_culture_matcher_streamlit.py


import pandas as pd
import streamlit as st
from datetime import datetime
import io
from collections import Counter
import re

# 날짜 자동 인식
def fix_time_format(val):
    val_str = str(val)
    
    # 시간 정보가 붙은 형식에서 잘못된 6자리 숫자만 시간으로 고치기
    # 예: "2025-03-08 075844" 또는 "2025-03-08 07:5844" → "2025-03-08 07:58:44"
    match = re.match(r'(.*\s)(\d{2}):?(\d{2})(\d{2})$', val_str)
    if match:
        return f"{match.group(1)}{match.group(2)}:{match.group(3)}:{match.group(4)}"
    
    # 혹시 그냥 6자리 숫자만 있는 경우에도 대응
    match2 = re.match(r'(\d{2})(\d{2})(\d{2})$', val_str)
    if match2:
        return f"{match2.group(1)}:{match2.group(2)}:{match2.group(3)}"
    
    return val_str
    
def parse_dates_safe(series):
    known_formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y",
        "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d %H%M",
        "%Y/%m/%d %H%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"
    ]
    def try_parse(val):
        if pd.isna(val): return pd.NaT
        val = fix_time_format(val)  # 👈 여기 추가
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
st.markdown("<h1 style='text-align:center;'>👶 NICU KONIS<br>타당도 조사 도우미</h1>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:right; font-size: 0.9em; color: gray;'>"
    "<a href='https://github.com/choi-doubley/konis_nicu/blob/main/KONIS_NICU_streamlit_manual.pdf?raw=T' target='_blank'>매뉴얼 다운로드</a><br>"
    "최종 업데이트: 2025-05-08<br>" 
    "문의: cyypedr@gmail.com"
    "</div>",
    unsafe_allow_html=True
)
#    "<a href='https://github.com/choi-doubley/konis_nicu/blob/main/KONIS_NICU_streamlit_manual.pdf?raw=T' target='_blank'>매뉴얼 다운로드</a><br>"

# 파일 업로드
culture_file = st.file_uploader("🧫 혈액배양 파일", type=["xlsx"])
icu_file = st.file_uploader("👶 중환자실 입퇴실 파일", type=["xlsx"])
bsi_file = st.file_uploader("🚨 KONIS WRAP 등록환자 파일 (optional)", type=["xlsx"])
info_file = st.file_uploader("📄 추가 환자정보 파일 (optional)", type=["xlsx"])

if icu_file and culture_file:
    icu_df = pd.read_excel(icu_file, dtype=str)
    culture_df = pd.read_excel(culture_file, dtype=str)
    bsi_df = pd.read_excel(bsi_file, dtype=str) if bsi_file else pd.DataFrame()
    info_df = pd.read_excel(info_file, dtype=str) if info_file else pd.DataFrame()

    st.subheader("🧫 혈액배양 파일 컬럼 선택")
    culture_id = st.selectbox("🆔 환자 ID", culture_df.columns, index=culture_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], culture_df.columns) or culture_df.columns[0]))
    use_ward_col = st.checkbox("❔ 시행병동 정보가 없습니다", value=False)
    use_ward_col = not use_ward_col
    if use_ward_col:
        culture_ward = st.selectbox("🚼 병동(시행부서)", culture_df.columns, index=culture_df.columns.get_loc(find_column(["병동", "부서"], culture_df.columns) or culture_df.columns[0]))
    culture_date = st.selectbox("📅 혈액배양 의뢰일", culture_df.columns, index=culture_df.columns.get_loc(find_column(["시행일", "채취일", "검사일","접수일"], culture_df.columns) or culture_df.columns[0]))
    use_result_col = st.checkbox("❔ 분리균 정보가 없습니다", value=False)
    use_result_col = not use_result_col
    if use_result_col:
        culture_result = st.selectbox("🦠 혈액배양 결과(분리균) 컬럼", culture_df.columns, index=culture_df.columns.get_loc(find_column(["미생물","결과"], culture_df.columns) or culture_df.columns[0]))

    if not bsi_df.empty:
        st.subheader("🚨 KONIS WRAP 등록환자 컬럼 선택")
        bsi_id_col = st.selectbox("🆔 환자 ID", bsi_df.columns,
            index=bsi_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], bsi_df.columns) or bsi_df.columns[0])
        )
        
    st.subheader("🧸 중환자실 파일 컬럼 선택")
    icu_id = st.selectbox("🆔 환자 ID 컬럼", icu_df.columns, index=icu_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid", "patient_id"], icu_df.columns) or icu_df.columns[0]))
    icu_in = st.selectbox("📅 입실일", icu_df.columns, index=icu_df.columns.get_loc(find_column(["입실"], icu_df.columns) or icu_df.columns[0]))
    icu_out = st.selectbox("📅 퇴실일", icu_df.columns, index=icu_df.columns.get_loc(find_column(["퇴실"], icu_df.columns) or icu_df.columns[0]))



    # 병합에 사용할 전체 후보 파일
    all_column_sources = {
        "중환자실 파일": icu_df,
        "혈액배양 파일": culture_df
    }

    if not bsi_df.empty:
        all_column_sources["BSI 파일"] = bsi_df
    
    if not info_df.empty:
        all_column_sources["추가정보 파일"] = info_df

    # 항상 "혈액배양 파일"을 첫 번째로 보이도록 재정렬
    all_column_options = ["혈액배양 파일"] + [k for k in all_column_sources.keys() if k != "혈액배양 파일"]

    st.markdown("---")
    st.markdown("### 📅 생년월일 정보")
    birth_unavailable = st.checkbox("❔ 생년월일 정보가 없습니다", value=False)
    if not birth_unavailable:
        birth_source = st.selectbox("📁 생년월일이 있는 파일", all_column_options, key="birth_src", index=0)
        birth_df = all_column_sources[birth_source]
        birth_id_col = st.selectbox("🆔 환자 ID 컬럼", birth_df.columns, key="birth_id", index=birth_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], birth_df.columns) or birth_df.columns[0]))
        birth_col = st.selectbox("📅 생년월일 컬럼", birth_df.columns, key="birth_col", index=birth_df.columns.get_loc(find_column(["생년월일", "birthdate", "dob"], birth_df.columns) or birth_df.columns[0]))

    #st.markdown("---")
    #st.markdown("### 👶 이름 정보")
    #name_source = st.selectbox("📁 이름이 있는 파일", all_column_options, key="name_src", index=0)
    #name_df = all_column_sources[name_source]
    #name_id_col = st.selectbox("🔑 환자 ID 컬럼", name_df.columns, key="name_id", index=name_df.columns.get_loc(find_column(["환자번호", "병록번호", "patientid"], name_df.columns) or name_df.columns[0]))
    #name_col = st.selectbox("🧒 이름 컬럼", name_df.columns, key="name_col", index=name_df.columns.get_loc(find_column(["환자명","이름", "성명", "name"], name_df.columns) or name_df.columns[0]))

    st.markdown("---")
    st.markdown("### 👦👧 성별 정보")
    gender_source = st.selectbox("📁 성별이 있는 파일", all_column_options, key="gender_src", index=0)
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

        merged = merged.drop_duplicates(subset=[culture_id, culture_date, culture_result] if use_result_col else [culture_id, culture_date])
        merged['surv_window'] = None


        # 1. 입실일 없는 경우 → 입퇴실일 확인
        merged.loc[merged['icu_in_day'].isna(), 'surv_window'] = "시행부서 확인"


        # 2. 감시기간 포함 (icu_day_start ≤ culture_date_day ≤ icu_day_end or icu_day_end isna)
        condition_matched = (
            (merged['icu_day_start'].notna()) &
            (merged['culture_date_day'] >= merged['icu_day_start']) &
            (
                (merged['culture_date_day'] <= merged['icu_day_end']) |
                (merged['icu_day_end'].isna())
            )
        )
        merged.loc[condition_matched, 'surv_window'] = None  # matched → 비고 없음

        # 3. 감시기간 이전 (culture_date_day < icu_day_start) → 감시기간 이전
        condition_before = (
            merged['icu_in_day'].notna() &
            (merged['culture_date_day'] >= merged['icu_in_day']) &
            (merged['culture_date_day'] < merged['icu_day_start'])
        )
        merged.loc[condition_before, 'surv_window'] = "감시기간 이전"

        # 4. 감시기간 이후 (culture_date_day > icu_day_end) → 감시기간 이후
        condition_after = (
            merged['icu_day_end'].notna() &
            (merged['culture_date_day'] > merged['icu_day_end'])
        )
        merged.loc[condition_after, 'surv_window'] = "감시기간 이후"

        # matched: 비고가 None인 것
        matched = merged[merged['surv_window'].isna()]

        # unmatched: 나머지 비고가 있는 행
        unmatched = merged[merged['surv_window'].notna()]

        # result = matched + unmatched로 culture_df의 모든 데이터 유지
        result = pd.concat([matched, unmatched], ignore_index=True, sort=False)


        # 이름, 성별 병합 전에 중복가능성 있는 열 제거
        gender_col_name = gender_col if not use_combined else combined_col
        #for col in [name_col, "이름", gender_col_name, "성별"]:
        #    if col in result.columns:
        #        result.drop(columns=[col], inplace=True)
        
        # 이름 초성 변환 병합
        #name_df = name_df[[name_id_col, name_col]].copy()
        #name_df = name_df.drop_duplicates(subset=[name_id_col], keep="last") ## 마지막 이름을 남김
        #name_df['name_initial'] = name_df[name_col].apply(get_initials)
        #result = result.merge(name_df[[name_id_col, 'name_initial']], left_on=culture_id, right_on=name_id_col, how='left')

        # 성별 병합     
        if use_combined:
            comb_df = gender_df[[gender_id_col, combined_col]].copy()
            comb_df = comb_df.drop_duplicates(subset=[gender_id_col])
            if position == "앞":
                comb_df['gender'] = comb_df[combined_col].str.split(delimiter).str[0]
            else:
                comb_df['gender'] = comb_df[combined_col].str.split(delimiter).str[-1]
            result = result.merge(comb_df[[gender_id_col, 'gender']], left_on=culture_id, right_on=gender_id_col, how='left')
        else:
            gender_df = gender_df.drop_duplicates(subset=[gender_id_col])
            gender_df = gender_df[[gender_id_col, gender_col]].rename(columns={gender_col: 'gender'})
            result = result.merge(gender_df, left_on=culture_id, right_on=gender_id_col, how='left')

        # 생년월일 병합 (선택적)
        birth_column_success = False ## 기본값 설정
        if not birth_unavailable:
            for col in [birth_col, "생년월일"]:
                if col in result.columns:
                    result.drop(columns=[col], inplace=True)               
            try:
                birth_df = birth_df[[birth_id_col, birth_col]].copy()
                birth_df = birth_df.drop_duplicates(subset=[birth_id_col])

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
                        result = result.merge(birth_df, left_on=culture_id, right_on=birth_id_col, how='left')
                        result.rename(columns={birth_col: "dob"}, inplace=True)
                        birth_column_success = birth_col in result.columns ## boolean

            except Exception as e:
                st.warning(f"⚠️ 생년월일 병합에 실패했습니다: {e}")


        # 날짜 포맷을 yyyy-mm-dd로 통일
        date_cols = [icu_in, icu_out, culture_date]
        if not birth_unavailable:
            date_cols.append("dob")

        for col in date_cols:
            if col in result:
                result[col] = pd.to_datetime(result[col], errors="coerce").dt.strftime("%Y-%m-%d")

        result = result.drop_duplicates(subset=[culture_id, culture_date, culture_result] if use_result_col else [culture_id, culture_date])        



        # 기존 "비고" 컬럼이 존재하면 삭제
        # 비고 컬럼 추가: NICU/신생아 포함 + ICU 입실정보가 없는 경우
        if "비고" in result.columns:
            result.drop(columns=["비고"], inplace=True)            

        if use_ward_col and 'culture_ward' in locals() and culture_ward:
            result.loc[
                result[culture_ward].str.contains("NICU|NR|신생아", na=False) & result[icu_in].isna(),
                "surv_window"
            ] = "입퇴실일 확인"


        # 정렬 및 일련번호
        surv_window_sort = {
            None: 0,
            "입퇴실일 확인": 1,
            "감시기간 이전": 2,
            "감시기간 이후": 3
        }
        result["order_sort"] = result["surv_window"].map(surv_window_sort)

        # 정렬 및 일련번호
        result_sorted = result.sort_values(
            by=["order_sort", culture_date, icu_in],
            ascending=[True, True, True],
            na_position="last"
        ).drop(columns=["order_sort"])
        result_sorted.insert(0, "No", range(1, len(result_sorted) + 1))

        # KONIS 등록여부 병합
        if not bsi_df.empty and 'bsi_id_col' in locals():
            result_sorted["KONIS"] = result_sorted[culture_id].isin(bsi_df[bsi_id_col]).map({True: "Y", False: "N"})
            #result_sorted.rename(columns={"KONIS": "등록여부"}, inplace=True)
    
        # 환자ID를 문자열로 강제 변환
        result_sorted[culture_id] = result_sorted[culture_id].astype(str)
        
        # 결측 컬럼 처리
        if use_result_col and 'culture_result' in locals() and culture_result:
            result_sorted["culture_result2"]=result_sorted[culture_result]
        else: 
            result_sorted["culture_result2"]=None

        if use_ward_col and 'culture_ward' in locals() and culture_ward:
            result_sorted["culture_ward2"]=result_sorted[culture_ward]
        else: 
            result_sorted["culture_ward2"]=None           
       
        column_rename_map = {
            "No": "번호",
            culture_id: "등록번호_ID",
            #"name_initial": "이름_초성",
            "gender": "성별",
            "dob": "생년월일",
            icu_in: "입실일",
            icu_out: "퇴실일",
            culture_date: "혈액배양 의뢰일",
            "culture_result2": "혈액배양 분리균",
            "KONIS": "KONIS WRAP 등록여부",
            "culture_ward2": "혈액배양 시행병동",
            "surv_window": "비고"
        }

        for col in column_rename_map.keys():
            if col not in result_sorted.columns:
                result_sorted[col] = ""

        # 필요한 컬럼만 선택
        export_df = result_sorted[list(column_rename_map.keys())].rename(columns=column_rename_map) # 기본(외부 타당도 조사용)
        export_df2 = export_df.copy()
        insert_loc = export_df2.columns.get_loc("혈액배양 분리균") + 1
        export_df2.insert(insert_loc, "BSI 분류", "") # 내부 타당도 조사용
        
        st.session_state["export_df1"] = export_df  
        st.session_state["export_df2"] = export_df2  
        st.session_state["matching_done"] = True

    if st.session_state.get("matching_done", False):
        st.success("✅ 매칭 완료! 결과 미리보기")
        st.dataframe(st.session_state["export_df1"], use_container_width=True, hide_index=True)
        #st.dataframe(export_df, use_container_width=True)

        # 다운로드 버튼 1
        output1 = io.BytesIO()
        with pd.ExcelWriter(output1, engine="openpyxl") as writer:
            st.session_state["export_df1"].astype({"등록번호_ID": str}).to_excel(writer, index=False)
        output1.seek(0)
        st.download_button("📥 결과 다운로드 - 외부 타당도 조사용 (.xlsx)", data=output1,
                           file_name="matched_result_external.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


        output2 = io.BytesIO()
        with pd.ExcelWriter(output2, engine="openpyxl") as writer:
            st.session_state["export_df2"].astype({"등록번호_ID": str}).to_excel(writer, index=False)
        output2.seek(0)
        st.download_button("📥 결과 다운로드 - 내부 타당도 조사용 (.xlsx)", data=output2,
                           file_name="matched_result_internal.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
