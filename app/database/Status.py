import os
import time
import requests
import sys
from dotenv import load_dotenv
import shutil
from Utilities import (
    generate_prompt,
    get_json,
    save_json_to_excel,
    inject_standardized_json_to_excel
)

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from shared_database import db

# Load environment
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

############ Look here is the path correct?############

EXCEL_REL_PATH = os.getenv("EXCEL_FILE_PATH", "extractions/ExcelTemplate.xlsx")
EXCEL_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", EXCEL_REL_PATH))

# Default values for Ollama API
DEFAULT_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "deepseek-r1:14b"

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", DEFAULT_API_URL)
MODEL_NAME = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

# Create extractions directory
extractions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "extractions")
os.makedirs(extractions_dir, exist_ok=True)

# Create debug output directory for raw responses
debug_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(debug_dir, exist_ok=True)

# Maximum retries before marking a job as failed
MAX_RETRIES = 3

# Go up from /app/database to /app
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXTRACTIONS_DIR = os.path.join(BASE_DIR, "extractions")
TEMPLATE_EXCEL_PATH = os.path.join(EXTRACTIONS_DIR, "ExcelTemplate.xlsx")
EXCEL_PATH = os.path.join(EXTRACTIONS_DIR, "extracted_data.xlsx")

# Debug
print("TEMPLATE PATH:", TEMPLATE_EXCEL_PATH)

if not os.path.exists(TEMPLATE_EXCEL_PATH):
    raise FileNotFoundError(f"ExcelTemplate.xlsx not found at: {TEMPLATE_EXCEL_PATH}")

os.makedirs(EXTRACTIONS_DIR, exist_ok=True)
if not os.path.exists(EXCEL_PATH):
    shutil.copy(TEMPLATE_EXCEL_PATH, EXCEL_PATH)


# --- Main Processing Function ---

def process_pending_jobs():
    print(f"Starting background job processor... Using model: {MODEL_NAME}")
    print(f"API endpoint: {OLLAMA_API_URL}")

    while True:
        try:
            pending_jobs = db.get_pending_jobs()
            if pending_jobs:
                print(f"Found {len(pending_jobs)} pending jobs to process")

            for job in pending_jobs:
                job_id = job['id']
                pdf_filename = job['pdf_filename']
                word_filename = job['word_filename']
                pdf_text = job["pdf_content"]
                word_text = job["word_content"]

                print(f"Processing job {job_id}: {pdf_filename} + {word_filename}")
                db.update_job_status(job_id, "processing")

                retries = 0
                while retries < MAX_RETRIES:
                    try:
                        prompt = generate_prompt(pdf_text, word_text)
                        print(f"Sending request to LLM API (attempt {retries+1})...")

                        api_url = OLLAMA_API_URL
                        if not api_url.endswith('/api/generate'):
                            api_url = api_url.rstrip('/') + '/api/generate'

                        response = requests.post(
                            api_url,
                            json={
                                "model": MODEL_NAME,
                                "prompt": prompt,
                                "stream": False
                            },
                            headers={"Content-Type": "application/json"},
                            timeout=300
                        )

                        if response.status_code != 200:
                            raise Exception(f"API returned status code {response.status_code}: {response.text}")

                        response_data = response.json()
                        response_text = response_data.get('response', '')
                        if not response_text:
                            raise ValueError("Empty response from LLM API")

                        print(f"First pass complete. Parsing response...")

                        # Extract final clean JSON
                        json_data = get_json(response_text.strip())
                        if not json_data:
                            raise ValueError("No valid JSON extracted from response")

                        #Save to Excel
                        TEMPLATE_PATH = os.getenv("EXCEL_TEMPLATE_PATH", "templates/Excel_template.xlsx")
                        OUTPUT_PATH = os.path.join(extractions_dir, "Final_Applications_Export.xlsx")

                        try:
                            inject_standardized_json_to_excel(json_data, TEMPLATE_PATH, OUTPUT_PATH)
                        except Exception as excel_err:
                            raise Exception(f"Excel generation failed: {excel_err}")


                        # Save successful job
                        db.update_job_status(
                            job_id, 
                            "done",
                            extracted_data=json_data,
                            excel_file=OUTPUT_PATH,
                            debug_output={
                                "model": MODEL_NAME,
                                "prompt_length": len(prompt),
                                "response_length": len(response_text),
                                "raw_response": response_text
                            }
                        )
                        print(f"Job {job_id} completed successfully!")
                        break

                    except Exception as processing_error:
                        print(f"Error processing job {job_id} (attempt {retries+1}): {str(processing_error)}")
                        retries += 1

                        if retries >= MAX_RETRIES:
                            db.update_job_status(
                                job_id, 
                                "failed",
                                debug_output={"error": str(processing_error)}
                            )
                            print(f"Job {job_id} marked as failed after {MAX_RETRIES} attempts")
                        else:
                            time.sleep(3)

            time.sleep(5)

        except Exception as e:
            print(f"Error in main processing loop: {e}")
            time.sleep(10)