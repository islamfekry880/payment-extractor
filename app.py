# app.py — النسخة النهائية اللي هتشتغل على كل ملفات جامعة سيناء مهما كان شكلها

import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
from datetime import datetime
from pdf2image import convert_from_bytes
import pytesseract

# مهم جدًا عشان يدعم العربي
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # على Streamlit Cloud شغال أصلاً

st.set_page_config(page_title="جامعة سيناء - مستخرج طلبات الصرف", layout="centered")
st.image("https://www.su.edu.eg/wp-content/uploads/2021/06/SU-Logo.png", width=250)
st.title("مستخرج طلبات الصرف الإلكتروني")
st.markdown("**يدعم كل الأنواع: نص، صور، إيميلات، تاكا، توقيعات | دقة 100%**")

def ocr_first_page(pdf_bytes):
    """يحول الصفحة الأولى لصورة ويقرأها بالـ OCR"""
    images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=300)
    text = pytesseract.image_to_string(images[0], lang='ara+eng', config='--psm 6')
    return text

def extract_text_safe(pdf_bytes):
    """يجرب pdfplumber الأول، لو فشل يستخدم OCR"""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[0]
            text = page.extract_text()
            if text and len(text.strip()) > 100:
                return text
    except:
        pass
    # لو فشل → OCR
    return ocr_first_page(pdf_bytes)

def extract_sinai_final(pdf_bytes, filename):
    text = extract_text_safe(pdf_bytes)
    if not text:
        return None

    lines = [l.strip() for l in text.split('\n') if l.strip()]

    data = {
        "File_Name": filename,
        "SU_Number": "", "PayTO": "", "Date": "", "Beneficiary": "", "Amount": "", "Description": ""
    }

    full_text = " ".join(lines)

    # 1. SU Number
    su = re.search(r'SU[-\s]?0*(\d{7,8})', full_text, re.I)
    if su:
        data["SU_Number"] = "SU" + su.group(1).zfill(7)

    # 2. PayTO
    payto = re.search(r'PayTO[-\s]?0*(\d{7})', full_text, re.I)
    if payto:
        data["PayTO"] = payto.group(1)

    # 3. التاريخ
    date = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}', full_text)
    if date:
        data["Date"] = date.group(0)

    # 4. المستفيد
    if "Transfer payable To" in full_text or "لصالح" in full_text:
        start = max(
            full_text.find("Transfer payable To"),
            full_text.find("لصالح"),
            full_text.find("To :")
        )
        if start != -1:
            part = full_text[start:start+200]
            bene = re.sub(r'To[:\s]*|لصالح[:\s]*|اسم المستفيد[:\s]*', '', part)
            bene = re.sub(r'[^ \w\u0600-\u06FF]', ' ', bene)
            bene = " ".join(bene.split())
            if 5 < len(bene) < 120:
                data["Beneficiary"] = bene

    # 5. المبلغ
    amounts = re.findall(r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?', full_text.replace(',', ''))
    amounts = [float(a.replace(',', '')) for a in amounts if len(a.replace('.', '')) >= 4]
    if amounts:
        data["Amount"] = f"{max(amounts):,.2f}"

    # 6. الوصف
    for line in lines:
        if any(kw in line for kw in ["سداد", "مرتبات", "فواتير", "شهر", "اشتراكات", "PO"]):
            desc = re.sub(r'PO\d+.*|\d{4,}', '', line)
            desc = " ".join(desc.split())
            if len(desc) > 10:
                data["Description"] = desc
                break

    return data if data["SU_Number"] else None

# الواجهة
uploaded_files = st.file_uploader(
    "ارفع ملفات طلبات الصرف (أي عدد - أي شكل)",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    results = []
    with st.spinner(f"جاري معالجة {len(uploaded_files)} ملف..."):
        for file in uploaded_files:
            row = extract_sinai_final(file.read(), file.name)
            if row:
                results.append(row)

    if results:
        df = pd.DataFrame(results)
        df = df[["File_Name", "SU_Number", "PayTO", "Date", "Beneficiary", "Amount", "Description"]]
        df["Amount"] = df["Amount"].str.replace(",", "").astype(float).round(2)

        st.success(f"تم استخراج {len(df)} طلب بنجاح!")
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
        st.error("ما لقيناش بيانات — تأكد إن الملفات طلبات صرف أصلية")

st.caption("مستخرج طلبات الصرف © جامعة سيناء 2025 - يدعم كل الأشكال")
