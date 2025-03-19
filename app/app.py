import streamlit as st
import requests
import os
import json
import threading
from dotenv import load_dotenv
from Utilities import (
    extract_text_from_pdf,
    extract_text_from_word,
    generate_prompt,
    get_json,
    save_json_to_excel,
    flatten_json
)
from database.db_manager import DatabaseManager
from database.Status import process_pending_jobs

# Load environment variables from .env file
load_dotenv()

# Initialize database manager
db = DatabaseManager()

# Default Ollama API URL if not set in .env
DEFAULT_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "deepseek-r1:14b"  # Using deepseek-r1:14b model

# Load Ollama API URL from environment variable or use default
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", DEFAULT_API_URL)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

# Display model information
st.sidebar.info(f"Using model: {OLLAMA_MODEL}")
st.sidebar.info(f"API endpoint: {OLLAMA_API_URL}")

# Create extractions directory if it doesn't exist
extractions_dir = os.path.join(os.path.dirname(__file__), "extractions")
os.makedirs(extractions_dir, exist_ok=True)

# Start background processor in a separate thread
processor_thread = threading.Thread(target=process_pending_jobs, daemon=True)
processor_thread.start()

st.title("CV & Job Application Processor")
st.write("Upload a CV (PDF) and job application (Word) to extract structured information")

# Add tabs for different functionalities
tab1, tab2 = st.tabs(["Upload Documents", "View Previous Extractions"])

with tab1:
    # File uploaders for PDF and Word files
    pdf_file = st.file_uploader("Upload a CV (PDF)", type="pdf")
    word_file = st.file_uploader("Upload a Job Application (Word)", type="docx")

    if pdf_file and word_file:
        # Extract text from both documents
        pdf_text = extract_text_from_pdf(pdf_file)
        word_text = extract_text_from_word(word_file)

        # Display extracted text
        with st.expander("View Extracted Text"):
            st.text_area("PDF Text", pdf_text, height=200)
            st.text_area("Word Text", word_text, height=200)

        # Process button
        if st.button("Submit Job for Processing"):
            try:
                with st.spinner("Adding job to queue..."):
                    # Add job to the database with pending status
                    job_id = db.add_job(pdf_file.name, word_file.name, pdf_text, word_text)
                    st.success(f"Job {job_id} added to the queue! It will be processed in the background.")
                    st.info("Check the 'View Previous Extractions' tab for updates on processing status.")

            except Exception as e:
                st.error(f"Error adding job to queue: {str(e)}")

with tab2:
    st.header("Previous Extractions")
    
    # Add refresh button
    if st.button("↻ Refresh"):
        st.rerun()

    # Fetch all processed jobs from the database
    extractions = db.get_all_extractions()

    if not extractions:
        st.info("No previous extractions found.")
    else:
        for extraction in extractions:
            job_id = extraction.get("id")
            pdf_filename = extraction.get("pdf_filename")
            word_filename = extraction.get("word_filename")
            status = extraction.get("status")
            excel_file_path = extraction.get("excel_file_path")
            debug_output = extraction.get("debug_output")
            timestamp = extraction.get("timestamp")

            # Create a unique key for each expander
            with st.expander(f"{pdf_filename} - {timestamp}", expanded=(status == "processing")):
                st.write(f"**CV File:** {pdf_filename}")
                st.write(f"**Job Application:** {word_filename}")
                
                # Use different colors for different statuses
                status_color = {
                    "pending": "🟡",
                    "processing": "🔵",
                    "done": "🟢",
                    "failed": "🔴"
                }.get(status, "⚪")
                st.write(f"**Status:** {status_color} `{status}`")

                if status == "done" and excel_file_path and os.path.exists(excel_file_path):
                    with open(excel_file_path, "rb") as f:
                        st.download_button(
                            "Download Excel",
                            f,
                            file_name=f"{pdf_filename.replace('.pdf', '')}_results.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                elif status == "failed" and debug_output:
                    try:
                        error_msg = json.loads(debug_output).get("error", "Unknown error")
                        st.error(f"Error: {error_msg}")
                    except:
                        st.error(f"Error: {debug_output}")
                elif status in ["pending", "processing"]:
                    st.info("Job is being processed. Please wait or refresh to check the status.")
