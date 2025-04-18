import pandas as pd
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def parse_dates_safe(series):
    known_formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H%M",
        "%Y/%m/%d %H%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S"
    ]

    def try_parse(val):
        if pd.isna(val):
            return pd.NaT
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

class ICUJoinApp:
    def __init__(self, root):
        self.root = root
        self.root.title("혈액배양 양성 환자 - 중환자실 입실 정보 매칭기")

        self.icu_df = None
        self.culture_df = None

        frame1 = tk.LabelFrame(root, text="1. 엑셀 파일 불러오기")
        frame1.pack(fill="x", padx=10, pady=5)

        self.icu_btn = tk.Button(frame1, text="중환자실 입퇴실 파일 선택", command=self.load_icu_file)
        self.icu_btn.pack(side="left", padx=10, pady=5)

        self.culture_btn = tk.Button(frame1, text="혈액배양 양성 파일 선택", command=self.load_culture_file)
        self.culture_btn.pack(side="left", padx=10, pady=5)

        frame2 = tk.LabelFrame(root, text="2. 컬럼 선택")
        frame2.pack(fill="x", padx=10, pady=5)

        tk.Label(frame2, text="중환자실 ID").grid(row=0, column=0)
        tk.Label(frame2, text="입실일").grid(row=1, column=0)
        tk.Label(frame2, text="퇴실일").grid(row=2, column=0)

        self.icu_id_cb = ttk.Combobox(frame2, width=30)
        self.icu_admit_cb = ttk.Combobox(frame2, width=30)
        self.icu_discharge_cb = ttk.Combobox(frame2, width=30)
        self.icu_id_cb.grid(row=0, column=1, padx=5)
        self.icu_admit_cb.grid(row=1, column=1, padx=5)
        self.icu_discharge_cb.grid(row=2, column=1, padx=5)

        tk.Label(frame2, text="혈액배양 ID").grid(row=0, column=2)
        tk.Label(frame2, text="혈액배양 시행일").grid(row=1, column=2)

        self.culture_id_cb = ttk.Combobox(frame2, width=30)
        self.culture_date_cb = ttk.Combobox(frame2, width=30)
        self.culture_id_cb.grid(row=0, column=3, padx=5)
        self.culture_date_cb.grid(row=1, column=3, padx=5)

        frame3 = tk.Frame(root)
        frame3.pack(pady=10)
        self.run_btn = tk.Button(frame3, text="3. 매칭 실행 및 저장", command=self.run_merge)
        self.run_btn.pack()

    def load_icu_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if path:
            try:
                self.icu_df = pd.read_excel(path)
                cols = list(self.icu_df.columns)
                self.icu_id_cb['values'] = cols
                self.icu_admit_cb['values'] = cols
                self.icu_discharge_cb['values'] = cols
                messagebox.showinfo("성공", "중환자실 입퇴실 파일을 불러왔습니다.")
            except Exception as e:
                messagebox.showerror("오류", f"파일을 불러오는 중 오류가 발생했습니다:\n{e}")

    def load_culture_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if path:
            try:
                self.culture_df = pd.read_excel(path)
                cols = list(self.culture_df.columns)
                self.culture_id_cb['values'] = cols
                self.culture_date_cb['values'] = cols
                messagebox.showinfo("성공", "혈액배양 양성 파일을 불러왔습니다.")
            except Exception as e:
                messagebox.showerror("오류", f"파일을 불러오는 중 오류가 발생했습니다:\n{e}")

    def run_merge(self):
        try:
            icu_id = self.icu_id_cb.get()
            icu_admit = self.icu_admit_cb.get()
            icu_discharge = self.icu_discharge_cb.get()
            culture_id = self.culture_id_cb.get()
            culture_date = self.culture_date_cb.get()

            if None in (self.icu_df, self.culture_df) or not all([icu_id, icu_admit, icu_discharge, culture_id, culture_date]):
                messagebox.showwarning("입력 오류", "모든 파일과 컬럼을 선택해주세요.")
                return

            self.icu_df[icu_admit] = parse_dates_safe(self.icu_df[icu_admit])
            self.icu_df[icu_discharge] = parse_dates_safe(self.icu_df[icu_discharge])
            self.culture_df[culture_date] = parse_dates_safe(self.culture_df[culture_date])

            merged = self.culture_df.merge(
                self.icu_df[[icu_id, icu_admit, icu_discharge]],
                left_on=culture_id,
                right_on=icu_id,
                how='left'
            )

            matched = merged[
                (merged[culture_date] >= merged[icu_admit]) &
                (merged[culture_date] <= merged[icu_discharge])
            ]

            result = self.culture_df.merge(
                matched[[culture_id, culture_date, icu_admit, icu_discharge]],
                on=[culture_id, culture_date],
                how='left'
            )

            save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
            if save_path:
                result.to_excel(save_path, index=False)
                messagebox.showinfo("완료", f"결과가 저장되었습니다:\n{save_path}")

        except Exception as e:
            messagebox.showerror("실행 오류", f"매칭 과정에서 오류가 발생했습니다:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ICUJoinApp(root)
    root.mainloop()
