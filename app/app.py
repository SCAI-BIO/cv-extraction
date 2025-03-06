import streamlit as st
import PyPDF2
import os

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL")

st.title("PDF Processor")

uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

if uploaded_file:
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = "\n".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
    st.text_area("Extracted Text", text, height=300)

