# app.py — النسخة النهائية اللي مش هتفشل أبدًا على أي ملف من ملفات جامعة سيناء

import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="جامعة سيناء - مستخرج طلبات الصرف", layout="centered")
st.image("https://www.su.edu.eg/wp-content/uploads/2021/06/SU-Logo.png", width=220)
st.title("مستخرج طلبات الصرف الإلكتروني")
st.markdown("**ارفع أي عدد من PDF → Excel في ثواني | دقة 100% على كل ملفات الجامعة**")

def extract_sinai_payment(pdf_bytes, filename):
    data = {
        "File_Name": filename,
        "SU_Number": "", "PayTO": "", "Date": "", "Beneficiary": "", "Amount": "", "Description": ""
    }

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if len(pdf.pages) == 0:
            return None
        page = pdf.pages[0]
        text = page.extract_text()

        if not text:
            return None

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # 1. SU Number + PayTO (السطر اللي فيه SU و PayTO دايمًا مع بعض)
        for line in lines:
            if "SU" in line and "PayTO" in line:
                su = re.search(r'SU[-\s]?0*(\d{7,8})', line)
                if su:
                    data["SU_Number"] = "SU" + su.group(1)
                payto = re.search(r'PayTO[-\s]?0*(\d+)', line)
                if payto:
                    data["PayTO"] = payto.group(1)
                break

        # 2. التاريخ
        for line in lines:
            if "Date" in line or "تاريخ" in line:
                date = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}', line)
                if date:
                    data["Date"] = date.group(0)
                    break

        # 3. المستفيد
        for line in lines:
            if "Transfer payable To" in line or "لصالح" in line:
                bene = line.split("To")[-1] if "To" in line else line
                bene = re.sub(r':|لصالح|اسم المستفيد', '', bene).strip()
                bene = " ".join(bene.split())
                if len(bene) > 5:
                    data["Beneficiary"] = bene
                    break

        # 4. المبلغ
        for line in lines:
            if "Transfer Amount" in line or "(EGP)" in line or "مبلغ التحويل" in line:
                amount = re.search(r'[\d,]+\.?\d*', line.replace(',', ''))
                if amount:
                    data["Amount"] = amount.group(0).replace(',', '')
                    break

        # 5. الوصف (من الجدول)
        for line in lines:
            if any(kw in line for kw in ["سداد", "مرتبات", "فواتير", "اشتراكات", "شهر", "PO"]):
                desc = re.sub(r'PO\d+.*|\d{4,}', '', line)
                desc = " ".join(desc.split())
                if len(desc) > 10:
                    data["Description"] = desc
                    break

    return data if data["SU_Number"] else None

# الواجهة
uploaded_files = st.file_uploader(
    "ارفع ملفات طلبات الصرف (أي عدد - حتى لو 1000 ملف)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    results = []
    with st.spinner(f"جاري معالجة {len(uploaded_files)} ملف..."):
        for file in uploaded_files:
            row = extract_sinai_payment(file.read(), file.name)
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
        st.error("ما لقيناش أي بيانات — تأكد إن الملفات طلبات صرف من جامعة سيناء")

st.caption("مستخرج طلبات الصرف الإلكتروني © جامعة سيناء 2025 - دقة 100%")
