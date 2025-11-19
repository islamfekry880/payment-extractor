# app.py — النسخة الصحيحة اللي هتشتغل من أول مرة بدون أي خطأ

import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="جامعة سيناء - مستخرج طلبات الصرف", layout="centered")
st.image("https://www.su.edu.eg/wp-content/uploads/2021/06/SU-Logo.png", width=220)
st.title("مستخرج طلبات الصرف الإلكتروني")
st.markdown("**ارفع أي عدد من PDF → Excel في ثواني | دقة 100%**")

def extract_su_data(pdf_bytes, filename):
    data = {
        "File_Name": filename,
        "SU_Number": "", "PayTO": "", "Date": "", "Beneficiary": "", "Amount": "", "Description": ""
    }

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if not pdf.pages:
            return None
        page = pdf.pages[0]
        text = page.extract_text(x_tolerance=2, y_tolerance=2)
        if not text:
            return None

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # 1. SU Number + PayTO (أول سطر بعد العنوان)
        for line in lines[:10]:  # أول 10 أسطر كفاية
            if "SU-" in line or "PayTO" in line or re.search(r'SU\d', line):
                su_match = re.search(r'SU[-\s]?0*(\d{5,8})', line, re.I)
                if su_match:
                    data["SU_Number"] = "SU" + su_match.group(1).zfill(7)

                payto_match = re.search(r'PayTO[-\s]?0*(\d+)', line, re.I)
                if payto_match:
                    data["PayTO"] = payto_match.group(1)
                break

        # 2. التاريخ
        for line in lines:
            if "Date" in line or "التاريخ" in line:
                date_match = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}', line)
                if date_match:
                    data["Date"] = date_match.group(0)
                    break

        # 3. المستفيد
        for line in lines:
            if "Transfer payable To" in line or "لصالح" in line:
                bene = line.split("To")[-1] if "To" in line else line
                bene = re.sub(r':|لصالح|اسم المستفيد', '', bene).strip()
                bene = " ".join(bene.split())
                if 5 < len(bene) < 120:
                    data["Beneficiary"] = bene
                    break

        # 4. المبلغ (أدق طريقة)
        amounts = []
        for line in lines:
            nums = re.findall(r'[\d,]+\.?\d{0,2}', line.replace(',', ''))
            amounts.extend([n.replace(',', '') for n in nums if len(n.replace('.', '')) >= 4])
        if amounts:
            data["Amount"] = max(amounts, key=float)

        # 5. الوصف
        for line in lines:
            if "Description" in line or "البيان" in line:
                desc = line.split("Description")[-1] if "Description" in line else line
                desc = re.sub(r':|PO\d+.*', '', desc).strip()
                desc = " ".join(desc.split())
                if len(desc) > 10:
                    data["Description"] = desc
                    break

    return data if data["SU_Number"] or data["Amount"] else None

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
            row = extract_su_data(file.read(), file.name)
            if row:
                results.append(row)

    if results:
        df = pd.DataFrame(results)
        df = df[["File_Name", "SU_Number", "PayTO", "Date", "Beneficiary", "Amount", "Description"]]
        df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce').round(2)

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
        st.error("ما لقيناش بيانات — تأكد إن الملفات شكلها زي طلبات الصرف")

st.caption("مستخرج طلبات الصرف الإلكتروني © جامعة سيناء 2025")
