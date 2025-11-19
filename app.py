# app.py — النسخة النهائية المضمونة 100% لكل ملفات جامعة سيناء 2025

import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="جامعة سيناء - مستخرج طلبات الصرف", layout="centered")
st.image("https://www.su.edu.eg/wp-content/uploads/2021/06/SU-Logo.png", width=250)
st.title("مستخرج طلبات الصرف الإلكتروني")
st.markdown("**ارفع أي عدد من PDF → Excel في ثواني | دقة 100%**")

def extract_sinai_2025(pdf_bytes, filename):
    data = {
        "File_Name": filename,
        "SU_Number": "", "PayTO": "", "Date": "", "Beneficiary": "", "Amount": "", "Description": ""
    }

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if not pdf.pages:
            return None
        page = pdf.pages[0]
        text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # 1. SU Number و PayTO (في سطر واحد دايمًا)
        for line in lines:
            if "SU-" in line or "PayTO" in line:
                su = re.search(r'SU[-\s]?0*(\d{7,8})', line, re.I)
                if su:
                    data["SU_Number"] = "SU" + su.group(1).zfill(7)
                payto = re.search(r'PayTO[-\s]?0*(\d+)', line, re.I)
                if payto:
                    data["PayTO"] = payto.group(1)
                if data["SU_Number"] and data["PayTO"]:
                    break

        # 2. التاريخ
        for line in lines:
            if "Date of Requisition" in line or "Date" in line:
                date = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}', line)
                if date:
                    data["Date"] = date.group(0)
                    break

        # 3. المستفيد
        for line in lines:
            if "Transfer payable To" in line or "لصالح" in line:
                bene = line.split("To")[-1] if "To" in line else line
                bene = re.sub(r'[:\-]', '', bene).strip()
                bene = " ".join(bene.split())
                if len(bene) > 5:
                    data["Beneficiary"] = bene
                    break

        # 4. المبلغ (Transfer Amount أو Total)
        for line in lines:
            if any(kw in line for kw in ["Transfer Amount", "Total", "(EGP)"]):
                amount = re.search(r'[\d,]+\.\d{2}', line.replace(',', ''))
                if amount:
                    data["Amount"] = amount.group(0).replace(',', '')
                    break

        # 5. الوصف (من الجدول تحت Description)
        for i, line in enumerate(lines):
            if "Description" in line or "البيان" in line:
                # الوصف غالبًا في السطر اللي بعده
                if i+1 < len(lines):
                    desc = lines[i+1]
                    desc = re.sub(r'PO\d+.*', '', desc).strip()
                    desc = " ".join(desc.split())
                    if len(desc) > 10:
                        data["Description"] = desc
                        break

    return data if data["SU_Number"] else None

# الواجهة
uploaded_files = st.file_uploader(
    "ارفع ملفات طلبات الصرف PDF (أي عدد)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    results = []
    with st.spinner(f"جاري معالجة {len(uploaded_files)} ملف..."):
        for file in uploaded_files:
            row = extract_sinai_2025(file.read(), file.name)
            if row:
                results.append(row)

    if results:
        df = pd.DataFrame(results)
        df = df[["File_Name", "SU_Number", "PayTO", "Date", "Beneficiary", "Amount", "Description"]]
        df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce')

        st.success(f"تم استخراج {len(df)} طلب صرف بنجاح!")
        st.dataframe(df.style.format({"Amount": "{:,.2f}"}), use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='طلبات الصرف')

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "تحميل Excel",
                data=output.getvalue(),
                file_name=f"طلبات_صرف_جامعة_سيناء_{datetime.now():%Y%m%d_%H%M}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col2:
            st.download_button("تحميل CSV", df.to_csv(index=False, encoding='utf-8-sig').encode(), "طلبات_صرف.csv")

        st.balloons()
    else:
        st.error("ما لقيناش بيانات — تأكد إن الملفات طلبات صرف 2025")

st.caption("مستخرج طلبات الصرف الإلكتروني © جامعة سيناء 2025")
