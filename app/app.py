import streamlit as st
from datetime import datetime
import requests
import os
import json
import threading
from dotenv import load_dotenv
from Utilities import (
    extract_text_from_pdf,
    extract_text_from_word,
    
)


import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Initialize database manager
from shared_database import db

from database.Status import process_pending_jobs

# Load environment variables from .env file
load_dotenv()


# Default Ollama API URL if not set in .env
DEFAULT_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "deepseek-r1:14b"  # Using mistral model

# Load Ollama API URL from environment variable or use default
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", DEFAULT_API_URL)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

# Display model information on the side
st.sidebar.info(f"Using model: {OLLAMA_MODEL}")
st.sidebar.info(f"API endpoint: {OLLAMA_API_URL}")

### Create extractions directory if it doesn't exist for the extracted files we can make one for each application
###with full name

extractions_dir = os.path.join(os.path.dirname(__file__), "extractions")
os.makedirs(extractions_dir, exist_ok=True)

# Start background processor in a separate thread (starts it in the background)
#demon True to stop if the tool was closed 
processor_thread = threading.Thread(target=process_pending_jobs, daemon=True)
processor_thread.start()

unique_key = "download_button_" + str(datetime.now().strftime("%Y%m%d%H%M%S"))

# Create the download button with the unique key
st.download_button(
    label="Download File",
    data="Here is the data you want to download",
    file_name="download.txt",
    mime="text/plain",
    key=unique_key  # Pass a unique key here
)

# Add tabs for different functionalities
tab1, tab2, tab3 = st.tabs(["Upload Documents", "View Previous Extractions","Bulk Upload"])

with tab1:
    # File uploaders for PDF and Word files
    pdf_file = st.file_uploader("Upload a CV (PDF or Word)", type=["pdf", "docx"])
    word_file = st.file_uploader("Upload a Job Application (Word)", type="docx")

    manual_word_text = st.text_area("Or paste the Job Application text here", height=200)
    st.caption("You can paste the job application instead of uploading a Word document.")

    if pdf_file and (word_file or manual_word_text):
        word_text = extract_text_from_word(word_file) if word_file else manual_word_text
         # Extract text based on file type
        if pdf_file.name.endswith(".pdf"):
            pdf_text = extract_text_from_pdf(pdf_file)
        elif pdf_file.name.endswith(".docx"):
            pdf_text = extract_text_from_word(pdf_file)
        else:
            st.error("Unsupported CV file type. Please upload a PDF or Word document.")
            pdf_text = ""


        with st.expander("View Extracted Text"):
            st.text_area("PDF Text", pdf_text, height=200)
            st.text_area("Job Application Text", word_text, height=200)

        if st.button("Submit Job for Processing"):
            try:
                with st.spinner("Adding job to queue..."):
                    job_id = db.add_job(
                        pdf_file.name,
                        word_file.name if word_file else "manual_input.txt",
                        pdf_text,
                        word_text
                    )
                    st.success(f"Job {job_id} added to the queue! It will be processed in the background.")
                    st.info("Check the 'View Previous Extractions' tab for updates on processing status.")
            except Exception as e:
                st.error(f"Error adding job to queue: {str(e)}")
    else:
        if not pdf_file:
            st.warning("Please upload a CV (PDF).")
        elif not (word_file or manual_word_text):
            st.warning("Please upload a job application (Word) or paste the text manually.")

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
                        if status == "done" and debug_output:
                            try:
                                debug_data = json.loads(debug_output)

                                # First agent download
                                if "raw_response" in debug_data:
                                    st.text_area("First LLM Response (Initial Extraction)", debug_data["raw_response"], height=200)
                                    st.download_button(
                                        label="⬇ Download First Agent Response",
                                        data=debug_data["raw_response"],
                                        file_name=f"job_{job_id}_first_agent.json",
                                        mime="application/json",
                                        key=f"download_first_{job_id}"
                                    )

                                # Second agent download
                                if "refined_response" in debug_data:
                                    st.text_area("Second LLM Response (Refined)", debug_data["refined_response"], height=200)
                                    st.download_button(
                                        label="⬇ Download Second Agent Response",
                                        data=debug_data["refined_response"],
                                        file_name=f"job_{job_id}_second_agent.json",
                                        mime="application/json",
                                        key=f"download_second_{job_id}"
                                    )

                            except Exception as e:
                                st.warning(f"Failed to load LLM debug data: {e}")


                       

                        # Show raw LLM response for debugging
                    if debug_output:
                        try:
                            debug_data = json.loads(debug_output)
                            if "raw_response" in debug_data:
                                    st.text_area("LLM Output", debug_data["raw_response"], height=1000)
                        except Exception as e:
                            st.warning(f"Failed to display raw response: {e}")
                elif status == "failed" and debug_output:
                    try:
                        error_msg = json.loads(debug_output).get("error", "Unknown error")
                        st.error(f"Error: {error_msg}")
                    except:
                        st.error(f"Error: {debug_output}")
                elif status in ["pending", "processing"]:
                    st.info("Job is being processed. Please wait or refresh to check the status.")

with tab3:
    st.header("Bulk Upload (Multiple CV + Application Pairs)")
    st.caption("Upload files in pairs: one CV (.pdf/.docx) and one application (.docx). Each pair will be processed as one job.")

    uploaded_files = st.file_uploader("Upload Files (PDF + DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

    if st.button("Submit Jobs from Uploaded Pairs"):
        if not uploaded_files or len(uploaded_files) < 2:
            st.warning("Please upload at least two files (one CV and one application).")
        else:
            submitted = 0
            unmatched = []

            # Group files in sets of two
            for i in range(0, len(uploaded_files), 2):
                pair = uploaded_files[i:i+2]
                if len(pair) != 2:
                    unmatched.append(pair[0].name)
                    continue

                # Identify CV and application
                cv_file = next((f for f in pair if f.name.lower().endswith(".pdf") or f.name.lower().endswith(".docx")), None)
                app_file = next((f for f in pair if f.name.lower().endswith(".docx")), None)

                if not cv_file or not app_file:
                    unmatched.extend([f.name for f in pair])
                    continue

                try:
                    pdf_text = extract_text_from_pdf(cv_file) if cv_file.name.endswith(".pdf") else extract_text_from_word(cv_file)
                    word_text = extract_text_from_word(app_file)

                    db.add_job(
                        pdf_filename=cv_file.name,
                        word_filename=app_file.name,
                        pdf_content=pdf_text,
                        word_content=word_text
                    )

                    preview = word_text[:40].replace("\n", " ") + ("..." if len(word_text) > 40 else "")
                    st.success(f"Job submitted: {cv_file.name} + {app_file.name}\nPreview: {preview}")
                    submitted += 1
                except Exception as e:
                    st.error(f"Failed to process files: {cv_file.name}, {app_file.name}\nReason: {e}")
                    continue

            if unmatched:
                st.warning(f"Some files were skipped: {', '.join(unmatched)}")

            if submitted:
                st.info(f"{submitted} job(s) added to the queue.")
            else:
                st.warning("No valid file pairs were submitted.")