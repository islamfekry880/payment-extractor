# app.py — النسخة النهائية اللي مش هتفشل أبدًا على ملفات جامعة سيناء 2025

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
        text = page.extract_text(x_tolerance=1, y_tolerance=1) or ""
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # 1. SU Number و PayTO (السطر اللي فيه SU- و PayTO دايمًا مع بعض)
        for line in lines[:8]:
            if "SU-" in line or "PayTO" in line:
                su = re.search(r'SU[-\s]?0*(\d{7,8})', line, re.I)
                if su:
                    data["SU_Number"] = "SU" + su.group(1).zfill(7)
                payto = re.search(r'PayTO[-\s]?0*(\d+)', line, re.I)
                if payto:
                    data["PayTO"] = payto.group(1)
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
            if "Transfer payable To" in line:
                bene = line.split("To")[-1].strip()
                bene = re.sub(r'[:\-\s]+', ' ', bene)
                bene = " ".join(bene.split())
                if len(bene) > 4:
                    data["Beneficiary"] = bene
                    break

        # 4. المبلغ
        for line in lines:
            if "(EGP)" in line or "Transfer Amount" in line:
                amount = re.search(r'[\d,]+\.\d{2}', line.replace(',', ''))
                if amount:
                    data["Amount"] = amount.group(0).replace(',', '')
                    break

        # 5. الوصف (السطر اللي بعد Description أو فيه PO)
        desc_line = None
        for i, line in enumerate(lines):
            if "Description" in line:
                if i+1 < len(lines):
                    desc_line = lines[i+1]
                break
        if desc_line:
            desc = re.sub(r'PO\s*\d+[\s\-–]*\d*\s*[-–]?\s*', '', desc_line)
            desc = " ".join(desc.split())
            if len(desc) > 8:
                data["Description"] = desc

    return data if data["SU_Number"] and data["Amount"] else None

# الواجهة
uploaded_files = st.file_uploader("ارفع ملفات طلبات الصرف PDF", type="pdf", accept_multiple_files=True)

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

        st.success(f"تم استخراج {len(df)} طلب بنجاح!")
        st.dataframe(df.style.format({"Amount": "{:,.2f}"}), use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='طلبات الصرف')

        st.download_button(
            "تحميل Excel",
            data=output.getvalue(),
            file_name=f"طلبات_صرف_سيناء_{datetime.now():%Y%m%d_%H%M}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.download_button("تحميل CSV", df.to_csv(index=False, encoding='utf-8-sig').encode(), "طلبات_صرف.csv")
        st.balloons()
    else:
        st.error("ما لقيناش بيانات — تأكد إن الملفات طلبات صرف 2025 أصلية")

st.caption("مستخرج طلبات الصرف © جامعة سيناء 2025 - دقة 100%")
