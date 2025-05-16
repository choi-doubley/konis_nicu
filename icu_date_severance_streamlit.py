## py -m streamlit run icu_date_severance_streamlit.py
import streamlit as st
import pandas as pd
import re
import io

st.title("환자 입퇴실일 계산기 (세브란스 양식)")

uploaded_files = st.file_uploader(
    "월별 입원 엑셀 파일을 모두 업로드하세요",
    type=["xlsx"],
    accept_multiple_files=True
)

def extract_year_month(filename):
    match = re.search(r"(\d{4})[_\-\.]?(0[1-9]|1[0-2])", filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    else:
        return "9999-99"  # 정렬상 맨 뒤로


# 자동 컬럼 탐색
def find_column(candidates, columns):
    for candidate in candidates:
        for col in columns:
            if candidate.lower().replace(" ", "") in col.lower().replace(" ", ""):
                return col
    return None

id_column = None
if uploaded_files:
    # 1. 파일 정렬
    uploaded_files = sorted(uploaded_files, key=lambda f: extract_year_month(f.name))

    # 첫 번째 파일로부터 id 변수 후보 탐색
    first_df = pd.read_excel(uploaded_files[0])
    col_candidates = ["연구등록번호", "등록번호", "환자ID", "환자번호", "병록번호","번호","id", "patientid"]
    default_id_col = find_column(col_candidates, first_df.columns)

    # Streamlit에서 사용자 지정 받기
    st.markdown("### 🔹 환자 식별자 컬럼 선택")
    id_column = st.selectbox(
        "환자 식별자에 해당하는 컬럼을 선택하세요:",
        options=first_df.columns.tolist(),
        index=first_df.columns.get_loc(default_id_col) if default_id_col in first_df.columns else 0
    )
    adm_yn = st.text_input("입원으로 간주할 값을 입력하세요 (예: 1, Y, 입원 등)", value="1")

    all_long = []
    for file in uploaded_files:
        filename = file.name
        try:
            df = pd.read_excel(file, dtype=str)
            # 날짜 컬럼: "2025.02.01(토)" 형식
            date_cols = [col for col in df.columns if re.match(r"\d{4}\.\d{2}\.\d{2}", str(col))]
            df_long = df.melt(
                id_vars=[id_column],
                value_vars=date_cols,
                var_name="날짜",
                value_name="재실여부"
            )
            # 날짜 문자열 변환 ("2025.02.01(토)" → datetime)
            df_long["날짜"] = pd.to_datetime(df_long["날짜"].str.extract(r"(\d{4}\.\d{2}\.\d{2})")[0], format="%Y.%m.%d")
            df_long["재실여부"] = (df_long["재실여부"].astype(str).str.strip() == adm_yn.strip()).astype(int)
            all_long.append(df_long)
        except Exception as e:
            st.error(f"{filename} 처리 중 오류 발생: {e}")

    # 2. 통합 및 정렬
    df_all = pd.concat(all_long, ignore_index=True)
    df_all = df_all.sort_values([id_column, "날짜"])
    min_date = pd.to_datetime(df_all["날짜"]).min()
    
    # 3. 입원 블록 구분
    def assign_block(df):
        df = df.copy()
        df["prev"] = df["재실여부"].shift(fill_value=0)
        df["new_block"] = (df["재실여부"] == 1) & (df["prev"] == 0)
        df["block_id"] = df["new_block"].cumsum()
        return df

    df_grouped = df_all.groupby([id_column]).apply(assign_block).reset_index(drop=True)

    # 4. 입퇴실일 계산
    result = (
        df_grouped[df_grouped["재실여부"] == 1]
        .groupby([id_column, "block_id"])
        .agg(입실일=("날짜", "min"), 퇴실일=("날짜", "max"))
        .reset_index()
        .sort_values([id_column, "입실일"])
    )

    result["입실일_dt"] = pd.to_datetime(result["입실일"])
    result["비고"] = ""
    result.loc[result["입실일_dt"] == min_date, "비고"] = "입실일 확인 필요"

    # 5. 컬럼 정리 및 출력
    result = result[[id_column, "입실일", "퇴실일", "비고"]]
    result["입실일"] = result["입실일"].dt.strftime('%Y-%m-%d')
    result["퇴실일"] = result["퇴실일"].dt.strftime('%Y' \
    '-%m-%d')
    st.success(f"총 {result.shape[0]}개의 입퇴원 구간이 감지되었습니다.")
    st.dataframe(result, hide_index=True)

    # 6. 다운로드
    # 엑셀 형식으로 다운로드용 파일 생성
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        result.to_excel(writer, index=False, sheet_name='입퇴원내역')

    output.seek(0)  # 
    processed_data = output.getvalue()

    st.download_button(
        label="입퇴실일 Excel 다운로드 (.xlsx)",
        data=processed_data,
        file_name="입퇴실일_결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )