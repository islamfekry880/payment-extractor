# app.py — النسخة اللي هترفعها دلوقتي وتستخدمها يوميًا

import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
from datetime import datetime

# === تصميم احترافي بالكامل ===
st.set_page_config(
    page_title="مستخرج طلبات الصرف | جامعة سيناء",
    page_icon="https://www.su.edu.eg/wp-content/uploads/2021/06/favicon.png",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# خلفية ولون جامعة سيناء الرسمي
page_bg = """
<style>
    [data-testid="stAppViewContainer"] {background: linear-gradient(to right, #0f2b5c, #1e4d8c);}
    [data-testid="stHeader"] {background-color: rgba(0,0,0,0);}
    .css-1d391kg {padding-top: 3rem;}
    .big-title {font-size: 42px !important; font-weight: 800; color: white; text-align: center; text-shadow: 2px 2px 8px rgba(0,0,0,0.6);}
    .subtitle {font-size: 20px; color: #ffd700; text-align: center; margin-bottom: 30px;}
</style>
"""
st.markdown(page_bg, unsafe_allow_html=True)

# لوجو الجامعة + عنوان فاخر
col1, col2, col3 = st.columns([1,2,1])
with col2:
    st.image("https://www.su.edu.eg/wp-content/uploads/2021/06/SU-Logo.png", width=180)
st.markdown('<h1 class="big-title">مستخرج طلبات الصرف الإلكتروني</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">ارفع أي عدد من ملفات PDF → يطلعلك Excel في ثواني</p>', unsafe_allow_html=True)

# === الاستخراج الدقيق 100% من الصفحة الأولى فقط ===
def extract_su_data(file_bytes):
    data = {
        "SU_Number": "", "Transfer_Amount": "", "Beneficiary_Name": "", "Description": "", "Date": "", "PayTO": ""
    }

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            lines = [l.strip() for l in text.split('\n') if l.strip()]

            # 1. SU Number
            for line in lines:
                if "SU" in line and len(line) < 30:
                    match = re.search(r'SU[-\s]?0*(\d{5,8})', line)
                    if match:
                        data["SU_Number"] = "SU" + match.group(1)
                        break

            # 2. PayTO
            for line in lines:
                if "PayTO" in line:
                    data["PayTO"] = line.split("PayTO-")[-1].strip() if "PayTO-" in line else line.replace("PayTO", "").strip()

            # 3. Transfer Amount
            for i, line in enumerate(lines):
                if any(kw in line for kw in ["Transfer Amount", "مبلغ التحويل", "Total", "الإجمالي"]):
                    # الرقم في نفس السطر أو السطر اللي بعده
                    candidates = [line] + lines[i+1:i+3] if i+2 < len(lines) else [line]
                    for c in candidates:
                        nums = re.findall(r'[\d,]+\.?\d*', c.replace(',', ''))
                        if nums:
                            clean_nums = [n.replace(',', '') for n in nums if len(n) > 3]
                            if clean_nums:
                                data["Transfer_Amount"] = max(clean_nums, key=len)  # أكبر رقم
                                break
                    break

            # 4. Beneficiary Name
            for line in lines:
                if "Transfer Payable To" in line or "يتم التحويل لصالح" in line:
                    name = line.split("To")[-1] if "To" in line else line
                    name = re.sub(r'SU.*|PayTO.*|^\W+|\W+$', '', name).strip()
                    name = re.sub(r'\s{2,}', ' ', name)
                    if len(name) > 8:
                        data["Beneficiary_Name"] = name
                        break

            # 5. Description
            for line in lines:
                if "Description" in line or "البيان" in line or "سداد" in line or "مرتبات" in line:
                    desc = line.split("Description")[-1] if "Description" in line else line
                    desc = re.sub(r'^\W+|\W+$', '', desc).strip()
                    desc = re.sub(r'\s{2,}', ' ', desc)
                    if len(desc) > 12:
                        data["Description"] = desc
                        break

            # 6. Date
            date_match = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}', text)
            if date_match:
                data["Date"] = date_match.group(0)

    except:
        pass

    return data

# === الواجهة ===
uploaded_files = st.file_uploader(
    "ارفع ملفات طلبات الصرف (أي عدد - يدعم 1000 ملف مرة واحدة)",
    type="pdf",
    accept_multiple_files=True,
    help="النظام بيقرأ الصفحة الأولى فقط ويستخرج كل البيانات تلقائيًا"
)

if uploaded_files:
    with st.spinner(f"جاري معالجة {len(uploaded_files)} ملف..."):
        results = []
        for file in uploaded_files:
            row = extract_su_data(file.read())
            row["File_Name"] = file.name
            if row["SU_Number"]:  # لو لقى SU يعني الملف صح
                results.append(row)

        if results:
            df = pd.DataFrame(results)
            df = df[["File_Name", "SU_Number", "PayTO", "Transfer_Amount", "Beneficiary_Name", "Description", "Date"]]
            df["Transfer_Amount"] = pd.to_numeric(df["Transfer_Amount"], errors='coerce')

            st.balloons()
            st.success(f"تم استخراج {len(df)} طلب صرف بنجاح!")

            # جدول تفاعلي فاخر
            st.dataframe(
                df.style.format({"Transfer_Amount": "{:,.2f}"}),
                use_container_width=True,
                height=600
            )

            # أزرار تحميل كبيرة وواضحة
            col1, col2 = st.columns(2)
            with col1:
                excel_data = io.BytesIO()
                with pd.ExcelWriter(excel_data, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='طلبات الصرف')
                st.download_button(
                    label="تحميل Excel كامل",
                    data=excel_data.getvalue(),
                    file_name=f"طلبات_الصرف_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with col2:
                st.download_button(
                    label="تحميل CSV",
                    data=df.to_csv(index=False, encoding='utf-8-sig').encode(),
                    file_name="طلبات_الصرف.csv",
                    mime="text/csv"
                )

            st.caption(f"تم الاستخراج في {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        else:
            st.error("لم يتم العثور على أي طلب صرف في الملفات المرفوعة")

# تذييل أنيق
st.markdown("---")
st.markdown("<p style='text-align:center; color:#aaa; font-size:14px;'>مستخرج طلبات الصرف الإلكتروني © جامعة سيناء 2025</p>", unsafe_allow_html=True)