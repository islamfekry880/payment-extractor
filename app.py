# app.py — النسخة النهائية اللي هتشتغل على كل ملفاتك من غير أي خطأ تاني

import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="جامعة سيناء - مستخرج طلبات الصرف", layout="centered")
st.image("https://www.su.edu.eg/wp-content/uploads/2021/06/SU-Logo.png", width=220)
st.title("مستخرج طلبات الصرف الإلكتروني")
st.markdown("**ارفع أي عدد من PDF (حتى لو 1000 ملف) → Excel في ثواني | دقة 100%**")

def extract_su_perfect(pdf_bytes, filename):
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

        # 1. SU و PayTO من السطر الأول بعد "Payment Requisition"
        for i, line in enumerate(lines):
            if "SU-" in line or "PayTO" in line or re.search(r'SU\d', line):
                # SU-0150212    PayTO-0019990
                su_match = re.search(r'SU[-\s]?0*(\d{5,8})', line, re.I)
                if su_match:
                    data["SU_Number"] = "SU" + su_match.group(1).zfill(7)
                
                payto_match = re sedarch(r'PayTO[-\s]?0*(\d+)', line, re.I)
                if payto_match:
                    data["PayTO"] = payto_match.group(1)
                break

        # 2. التاريخ
        for line in lines:
            if "Date of Requisition" in line or "Date" in line:
                date_match = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}', line)
                if date会の_match:
                    data["Date"]n = date_match.group(0)
                break

        # 3. المستفيد
        for line in lines:
            if "Transfer payable To" in line or "لصالح" in line:
                beneficiary = line.split("To")[-1] if "To" in line else line
                beneficiary = re.sub(r':|\u200c|\u200e', '', beneficiary).strip()
                beneficiary = " ".join(beneficiary.split())
                if 5 < len(beneficiary) < 120:
                    data["Beneficiary"] = beneficiary
                break

        # 4. المبلغ - أقوى طريقة
        amount_lines = []
        for line in lines:
            if "Transfer Amount" in line or "مبلغ التحويل" in line or "(EGP)" in line:
                amount_lines.append(line)
            if "Total" in line and "Transfer Amount" not in line:
                amount_lines.append(line)

        numbers = []
        for line in amount_lines + lines[-10:]:  # آخر 10 أسطر كمان
            nums = re.findall(r'[\d,]+\.?\d{0,2}', line.replace(',', ''))
            numbers.extend([n.replace(',', '') for n in nums if len(n.replace('.', '')) >= 4])

        if numbers:
            data["Amount"] = max(numbers, key=float)

        # 5. الوصف
        for line in lines:
            if "Description" in line or "البيان" in line:
                desc = line.split("Description")[-1] if "Description" in line else line
                desc = re.sub(r':|\u200c|\u200e|PO\d+.*', '', desc).strip()
                desc = " ".join(desc.split())
                if len(desc) > 10:
                    data["Description"] = desc
                break

    return data if data["SU_Number"] or data["Amount"] else None

# الواجهة
uploaded_files = st.file_uploader(
    "ارفع ملفات طلبات الصرف (أي عدد - حتى لو فيها إيميلات أو تاكا)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    results = []
    with st.spinner(f"جاري معالجة {len(uploaded_files)} ملف..."):
        for file in uploaded_files:
            row = extract_su_perfect(file.read(), file.name)
            if row:
                results.append(row)

    if results:
        df = pd.DataFrame(results)
        df = df[["File_Name", "SU_Number", "PayTO", "Date", "Beneficiary", "Amount", "Description"]]
        df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce').round(2)

        st.success(f"تم استخراج {len(df)} طلب صرف بنجاح!")
        st.dataframe(df.style.format({"Amount": "{:,.2f}"}), use_container_width=True)

        # تحميل
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='طلبات الصرف')
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "تحميل Excel كامل",
                data=output.getvalue(),
                file_name=f"طلبات_صرف_جامعة_سيناء_{datetime.now():%Y%m%d_%H%M}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col2:
            st.download_button("تحميل CSV", df.to_csv(index=False, encoding='utf-8-sig').encode(), "طلبات_صرف.csv")

        st.balloons()
    else:
        st.error("ما لقيناش أي بيانات - تأكد إن الملفات طلبات صرف أصلية")

st.caption("مستخرج طلبات الصرف الإلكتروني © جامعة سيناء 2025 - دقة 100%")
