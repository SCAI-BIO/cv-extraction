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
    st.header("Bulk Upload (Multiple Applications)")
    st.caption("Upload matching CVs and Job Applications for batch processing.")

    # Upload CV files
    cv_files = st.file_uploader("Upload CVs (PDF or DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

    # Upload Job Application files or paste job application text
    app_files = st.file_uploader("Upload Job Applications (DOCX only)", type=["docx"], accept_multiple_files=True)
    manual_word_text = st.text_area("Or paste the Job Application text here for all CVs", height=200)
    st.caption("You can paste a common job application instead of uploading individual Word documents.")

    if st.button("Submit Bulk Jobs for Processing"):
        if not cv_files or (not app_files and not manual_word_text):
            st.error("Please upload CVs and Applications or provide pasted text.")
        else:
            try:
                with st.spinner("Matching and submitting jobs..."):
                    def get_key(file): return file.name.split('.')[0].split('_')[0].lower()
                    cv_map = {get_key(f): f for f in cv_files}
                    app_map = {get_key(f): f for f in app_files}

                    matched_keys = set(cv_map.keys()) & set(app_map.keys()) if app_files else set(cv_map.keys())

                    if not matched_keys:
                        st.error("No matching filename pairs found (e.g., john_cv.pdf and john_app.docx).")
                        st.stop()

                    submitted = 0
                    for key in matched_keys:
                        cv_file = cv_map[key]
                        app_file = app_map.get(key)

                        # Extract text from CV
                        if cv_file.name.endswith(".pdf"):
                            pdf_text = extract_text_from_pdf(cv_file)
                        else:
                            pdf_text = extract_text_from_word(cv_file)

                        # Handle job application text (either uploaded or pasted)
                        if app_file:
                            word_text = extract_text_from_word(app_file)
                        else:
                            # If no app file, use pasted text
                            word_text = manual_word_text

                        # Save the job application text as a file (if necessary)
                        if not app_file:  # For manual text, save as a unique file
                            manual_text_file = f"{key}_job_application.txt"
                            with open(manual_text_file, "w") as f:
                                f.write(word_text)
                            app_file = manual_text_file

                        # Add the job to the database
                        db.add_job(
                            pdf_filename=cv_file.name,
                            word_filename=app_file.name if isinstance(app_file, str) else app_file.name,
                            pdf_content=pdf_text,
                            word_content=word_text
                        )
                        
                        # Show preview of job application text (first 20 characters)
                        preview_text = word_text[:20] + ("..." if len(word_text) > 20 else "")
                        st.write(f"**{cv_file.name}** - **Job Application Preview:** {preview_text}")
                        
                        submitted += 1

                    st.success(f"{submitted} jobs added to the queue!")
                    st.info("They will be processed in the background. Check 'Previous Extractions' tab for status.")

            except Exception as e:
                st.error(f"Bulk processing failed: {str(e)}")
