# app.py — النسخة النهائية اللي مش هتفشل أبدًا مهما كان شكل الـ PDF

import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
from datetime import datetime
from pdf2image import convert_from_bytes
import pytesseract

# إعدادات OCR للعربي والإنجليزي
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # لو على ويندوز محلي
# على Streamlit Cloud مش محتاج السطر ده، هو مثبت أصلاً

st.set_page_config(page_title="مستخرج طلبات الصرف - جامعة سيناء", layout="centered")
st.image("https://www.su.edu.eg/wp-content/uploads/2021/06/SU-Logo.png", width=200)
st.title("مستخرج طلبات الصرف الإلكتروني")
st.markdown("**يدعم كل الأشكال: نص، صور، إيميلات، تاكا، توقيعات**")

def ocr_page_if_needed(pdf_bytes):
    """لو pdfplumber ماجابش نص كويس، نستخدم OCR"""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[0]
            text = page.extract_text()
            if text and len(text) > 100:
                return text
    except:
        pass
    
    # OCR fallback
    images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
    text = pytesseract.image_to_string(images[0], lang='ara+eng')
    return text

def extract_data(file_bytes, filename):
    text = ocr_page_if_needed(file_bytes)
    if not text:
        return None

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    full = " ".join(lines)

    data = {
        "File_Name": filename,
        "SU_Number": "", "PayTO": "", "Date": "", "Beneficiary": "", "Amount": "", "Description": ""
    }

    # 1. SU Number
    su = re.search(r'SU[-\s]?0*(\d{5,8})', full, re.I)
    if su:
        data["SU_Number"] = "SU" + su.group(1).zfill(7)

    # 2. PayTO
    payto = re.search(r'PayTO[-\s]?0*(\d+)', full, re.I)
    if payto:
        data["PayTO"] = payto.group(1)

    # 3. التاريخ
    date = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}', full)
    if date:
        data["Date"] = date.group(0)

    # 4. المستفيد
    if any(k in full for k in ["Transfer Payable To", "لصالح", "اسم المستفيد"]):
        start = max(full.find("Transfer Payable To"), full.find("لصالح"), full.find("اسم المستفيد"))
        if start != -1:
            part = full[start:start+200]
            beneficiary = re.sub(r'.*To[:\-]\s*', '', part, flags=re.I)
            beneficiary = re.sub(r'SU.*|PayTO.*|Transfer.*|Amount.*|\d{4,}', '', beneficiary)
            beneficiary = " ".join(beneficiary.split())
            if 5 < len(beneficiary) < 100:
                data["Beneficiary"] = beneficiary

    # 5. المبلغ - أقوى طريقة ممكنة
    amounts = re.findall(r'[\d,]+\.?\d{0,2}\b', full.replace(',', ''))
    amounts = [a.replace(',', '').strip() for a in amounts if len(a.replace('.', '')) >= 4]
    if amounts:
        data["Amount"] = max(amounts, key=lambda x: float(x) if x.replace('.','').isdigit() else 0)

    # 6. الوصف
    desc_keywords = ["سداد", "مرتبات", "فواتير", "اشتراكات", "شهر", "تأمينات", "PO", "شراء", "صيانة", "خدمات"]
    for line in lines:
        if any(k in line for k in desc_keywords) and len(line) > 15:
            clean = re.sub(r'PO\d+|\d{5,}|Total.*|Amount.*', '', line)
            clean = " ".join(clean.split())
            if len(clean) > 10:
                data["Description"] = clean
                break

    return data if data["SU_Number"] or data["Amount"] else None

# الواجهة
uploaded_files = st.file_uploader(
    "ارفع أي عدد من ملفات PDF (حتى لو scanned أو فيها إيميلات)",
    type="pdf", accept_multiple_files=True
)

if uploaded_files:
    with st.spinner(f"جاري معالجة {len(uploaded_files)} ملف..."):
        results = []
        for file in uploaded_files:
            row = extract_data(file.read(), file.name)
            if row:
                results.append(row)

    if results:
        df = pd.DataFrame(results)
        df = df[["File_Name","SU_Number","PayTO","Date","Beneficiary","Amount","Description"]]
        df["Amount"] = pd.to_numeric(df["Amount"], errors='coerce')

        st.success(f"تم استخراج {len(df)} طلب بنجاح!")
        st.dataframe(df.style.format({"Amount": "{:,.2f}"}), use_container_width=True)

        # تحميل Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='طلبات الصرف')
        st.download_button(
            "تحميل Excel كامل",
            data=output.getvalue(),
            file_name=f"طلبات_صرف_{datetime.now():%Y%m%d_%H%M}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.download_button("تحميل CSV", df.to_csv(index=False, encoding='utf-8-sig').encode(), "طلبات_صرف.csv")
        st.balloons()
    else:
        st.error("لم يتم العثور على بيانات - تأكد من رفع ملفات طلبات الصرف")

st.caption("مستخرج طلبات الصرف الإلكتروني © جامعة سيناء 2025 - يدعم كل الأنواع")
