import os
import time
import requests
import sys
import logging
from Utilities import build_refinement_prompt


# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from shared_database import db

from Utilities import generate_prompt, get_json, save_json_to_excel


logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Default values for Ollama API
DEFAULT_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "deepseek-r1:14b"  # Updated to use deepseek-r1:14b

# Load Ollama API URL from environment variable or use default
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", DEFAULT_API_URL)
MODEL_NAME = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

logger.info("=== CV Extraction Configuration ===")
logger.info(f"Model: {MODEL_NAME}")

# Create extractions directory
extractions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "extractions")
os.makedirs(extractions_dir, exist_ok=True)

# Maximum retries before marking a job as failed
MAX_RETRIES = 3

def process_pending_jobs():
    """Background job processor that handles pending extraction jobs."""
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
                            timeout=3000
                        )

                        if response.status_code != 200:
                            raise Exception(f"API returned status code {response.status_code}: {response.text}")

                        response_data = response.json()
                        response_text = response_data.get('response', '')
                        if not response_text:
                            raise ValueError("Empty response from LLM API")

                        print(f"First pass complete. Running refinement...")

                        #First-pass JSON
                        initial_json = response_text.strip()

                        #Run Second-Pass Refinement
                        refinement_prompt = build_refinement_prompt(initial_json, pdf_text, word_text)
                        refine_response = requests.post(
                            api_url,
                            json={
                                "model": MODEL_NAME,
                                "prompt": refinement_prompt,
                                "stream": False
                            },
                            headers={"Content-Type": "application/json"},
                            timeout=3000
                        )

                        if refine_response.status_code != 200:
                            raise Exception(f"Refinement failed: {refine_response.status_code}: {refine_response.text}")

                        refined_text = refine_response.json().get("response", "").strip()

                        if not refined_text:
                            raise ValueError("Empty refinement response")

                        # Final clean JSON
                        json_data = get_json(refined_text)
                        if not json_data:
                            raise ValueError("No valid JSON extracted from second-pass response")

                        #Save to Excel
                        excel_filename = f"extraction_{job_id}_{pdf_filename.replace('.pdf', '')}.xlsx"
                        excel_path = os.path.join(extractions_dir, excel_filename)
                        save_json_to_excel(json_data, excel_path)

                        # Save successful job
                        db.update_job_status(
                            job_id, 
                            "done",
                            extracted_data=json_data,
                            excel_file=excel_path,
                            debug_output={
                                "model": MODEL_NAME,
                                "prompt_length": len(prompt),
                                "response_length": len(refined_text),
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