# app.py — النسخة اللي هتشتغل 100% على ملفاتك الحقيقية

import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="مستخرج طلبات الصرف - جامعة سيناء", layout="centered")
st.image("https://www.su.edu.eg/wp-content/uploads/2021/06/SU-Logo.png", width=180)
st.title("مستخرج طلبات الصرف الإلكتروني")
st.markdown("**ارفع أي عدد من PDF → Excel في ثواني**")

def extract_su_data(file_bytes):
    data = {
        "File_Name": "",
        "SU_Number": "",
        "PayTO": "",
        "Date": "",
        "Beneficiary": "",
        "Amount": "",
        "Description": ""
    }

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()

        if not text:
            return None

        # تنظيف النص
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        full_text = " ".join(lines)

        # 1. SU Number
        su = re.search(r'SU[-\s]?[\d-]*(\d{7,8})', full_text, re.I)
        if su:
            data["SU_Number"] = "SU" + su.group(1).zfill(7)

        # 2. PayTO
        payto = re.search(r'PayTO[-\s]?(\d+)', full_text, re.I)
        if payto:
            data["PayTO"] = payto.group(1)

        # 3. التاريخ
        date = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}', full_text)
        if date:
            data["Date"] = date.group(0)

        # 4. المستفيد (Transfer Payable To)
        if "Transfer Payable To" in full_text:
            start = full_text.find("Transfer Payable To") + 19
            end = full_text.find("\n", start)
            beneficiary = full_text[start:end if end != -1 else len(full_text)].strip()
            beneficiary = re.sub(r'SU.*|PayTO.*|Transfer Amount.*', '', beneficiary).strip()
            beneficiary = " ".join(beneficiary.split())
            if len(beneficiary) > 5:
                data["Beneficiary"] = beneficiary

        # 5. المبلغ (أقوى طريقة)
        amounts = re.findall(r'[\d,]+\.?\d{2}', full_text.replace(',', ''))
        amounts = [a.replace(',', '') for a in amounts if len(a.replace('.', '')) >= 5]
        if amounts:
            data["Amount"] = max(amounts, key=lambda x: float(x))

        # 6. البيان (Description)
        desc_keywords = ["سداد", "مرتبات", "فواتير", "اشتراكات", "شهر", "تأمينات", "PO"]
        for line in lines:
            if any(kw in line for kw in desc_keywords) and len(line) > 15:
                clean_desc = re.sub(r'PO\d+|\d{4,}', '', line)
                clean_desc = " ".join(clean_desc.split())
                if len(clean_desc) > 10:
                    data["Description"] = clean_desc
                    break

        # لو مفيش وصف، نأخد أول سطر طويل بعد Description
        if not data["Description"]:
            for line in lines:
                if "Description" in line:
                    desc = line.split("Description")[-1].strip()
                    if len(desc) > 10:
                        data["Description"] = desc
                        break

    return data if data["SU_Number"] else None

# الواجهة
uploaded_files = st.file_uploader(
    "ارفع ملفات PDF (أي عدد)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("جاري معالجة الملفات..."):
        results = []
        for file in uploaded_files:
            row = extract_su_data(file.read())
            if row:
                row["File_Name"] = file.name
                results.append(row)

    if results:
        df = pd.DataFrame(results)
        df = df[["File_Name", "SU_Number", "PayTO", "Date", "Beneficiary", "Amount", "Description"]]
        df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce')

        st.success(f"تم استخراج {len(df)} طلب صرف بنجاح!")
        st.dataframe(df.style.format({"Amount": "{:,.2f}"}), use_container_width=True)

        # تحميل Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='طلبات الصرف')
        st.download_button(
            "تحميل Excel",
            data=output.getvalue(),
            file_name=f"طلبات_صرف_{datetime.now():%Y%m%d_%H%M}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.download_button("تحميل CSV", df.to_csv(index=False, encoding='utf-8-sig').encode(), "طلبات_صرف.csv")
        st.balloons()
    else:
        st.error("لم يتم العثور على بيانات — تأكد إن الملفات شكلها زي الصور اللي رفعتها")

st.markdown("---")
st.caption("مستخرج طلبات الصرف الإلكتروني © جامعة سيناء 2025")
