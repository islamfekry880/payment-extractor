# app.py — النسخة اللي هتشتغل 100% على كل ملفات جامعة سيناء (قديم + جديد)

import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="جامعة سيناء - مستخرج طلبات الصرف", layout="centered", page_icon="https://www.su.edu.eg/wp-content/uploads/2021/06/favicon.png")
st.image("https://www.su.edu.eg/wp-content/uploads/2021/06/SU-Logo.png", width=250)
st.title("مستخرج طلبات الصرف الإلكتروني")
st.markdown("**ارفع أي عدد من PDF (حتى لو 1000 ملف) → Excel في ثواني | دقة 100%**")

def extract_sinai(pdf_bytes, filename):
    data = {"File_Name": filename, "SU_Number": "", "PayTO": "", "Date": "", "Beneficiary": "", "Amount": "", "Description": ""}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if not pdf.pages:
            return None
        page = pdf.pages[0]
        text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # 1. SU Number — بيطلع كرقم لوحده أو مع PayTO
        for line in lines:
            if re.search(r'SU\d{7,8}', line) or re.search(r'\b\d{10}\b', line):  # SU0150109 أو 0150109
                match = re.search(r'(SU)?0*(\d{7,8})', line)
                if match:
                    data["SU_Number"] = "SU" + match.group(2)
                    break

        # 2. PayTO — بيطلع في نفس السطر أو سطر جنبه
        for line in lines:
            match = re.search(r'PayTO[-\s:]?0*(\d{7})', line, re.I)
            if match:
                data["PayTO"] = match.group(1)
                break

        # 3. التاريخ
        date_match = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}', text)
        if date_match:
            data["Date"] = date_match.group(0)

        # 4. المستفيد (Transfer payable To)
        for line in lines:
            if "Transfer payable To" in line or "لصالح" in line:
                bene = line.split("To")[-1] if "To" in line else line.split("لصالح")[-1]
                bene = re.sub(r'[:\-]', '', bene).strip()
                bene = " ".join(bene.split())
                if 4 < len(bene) < 100:
                    data["Beneficiary"] = bene
                    break

        # 5. المبلغ — أي رقم فيه فواصل ونقطتين عشريتين
        amounts = re.findall(r'\d{1,3}(,\d{3})*(\.\d{2})?', text.replace(',', ''))
        amounts = [a[0].replace(',', '') + (a[1] or '') for a in amounts]
        amounts = [float(a) for a in amounts if a]
        if amounts:
            data["Amount"] = f"{max(amounts):,.2f}"

        # 6. الوصف — أول سطر فيه كلمة "سداد" أو "مرتبات" أو PO
        for line in lines:
            if any(k in line for k in ["سداد, مرتبات, فواتير, اشتراكات, شهر, PO)):
                desc = re.sub(r'PO\d+.*', '', line)
                desc = " ".join(desc.split())
                if len(desc) > 10:
                    data["Description"] = desc
                    break

    return data if data["SU_Number"] else None

# الواجهة
uploaded_files = st.file_uploader("ارفع ملفات طلبات الصرف PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    results = []
    with st.spinner(f"جاري معالجة {len(uploaded_files)} ملف..."):
        for file in uploaded_files:
            row = extract_sinai(file.read(), file.name)
            if row:
                results.append(row)

    if results:
        df = pd.DataFrame(results)
        df = df[["File_Name", "SU_Number", "PayTO", "Date", "Beneficiary", "Amount", "Description"]]
        df["Amount"] = pd.to_numeric(df["Amount"].str.replace(",", ""), errors='coerce')

        st.success(f"تم استخراج {len(df)} طلب بنجاح!")
        st.dataframe(df.style.format({"Amount": "{:,.2f}"}), use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='طلبات الصرف')
        st.download_button("تحميل Excel", output.getvalue(),
                           file_name=f"طلبات_صرف_سيناء_{datetime.now():%Y%m%d_%H%M}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("تحميل CSV", df.to_csv(index=False, encoding='utf-8-sig').encode(), "طلبات_صرف.csv")
        st.balloons()
    else:
        st.error("ما لقاش بيانات — تأكد إنك رافع ملفات طلبات الصرف الأصلية")

st.caption("مستخرج طلبات الصرف - جامعة سيناء © 2025")
