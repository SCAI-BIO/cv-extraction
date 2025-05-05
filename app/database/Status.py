import os
import sys
import time
import shutil
import requests
import logging
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional, Dict, Any

from Utilities import (
    generate_prompt,
    get_json,
    inject_standardized_json_to_excel
)

# Add parent dir to path for shared_database import
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from shared_database import db

# Environment
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTIONS_DIR = os.path.join(BASE_DIR, "extractions")
TEMPLATE_EXCEL_PATH = os.path.join(EXTRACTIONS_DIR, "ExcelTemplate.xlsx")
OUTPUT_EXCEL_PATH = os.path.join(EXTRACTIONS_DIR, "Final_Applications_Export.xlsx")

# Ensure required folders exist
os.makedirs(EXTRACTIONS_DIR, exist_ok=True)

# Ensure template exists
if not os.path.exists(TEMPLATE_EXCEL_PATH):
    logger.error(f"Template not found: {TEMPLATE_EXCEL_PATH}")
    raise FileNotFoundError(f"Template not found: {TEMPLATE_EXCEL_PATH}")

# Create output file from template if needed
if not os.path.exists(OUTPUT_EXCEL_PATH):
    shutil.copy(TEMPLATE_EXCEL_PATH, OUTPUT_EXCEL_PATH)
    logger.info(f"Created output Excel file: {OUTPUT_EXCEL_PATH}")

# API setup
DEFAULT_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "deepseek-r1:14b"
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", DEFAULT_API_URL)
MODEL_NAME = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

MAX_RETRIES = 3


class Status:
    def __init__(self):
        self.db = db
        self.template_path = TEMPLATE_EXCEL_PATH
        self.output_path = OUTPUT_EXCEL_PATH

    def _generate_prompt(self, pdf_text: str, word_text: str) -> str:
        return generate_prompt(pdf_text, word_text)

    def _get_llm_response(self, prompt: str) -> str:
        try:
            logger.info("Sending request to LLM API...")
            response = requests.post(
                OLLAMA_API_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False
                },
                headers={"Content-Type": "application/json"},
                timeout=3000
            )
            if response.status_code != 200:
                raise Exception(f"API returned {response.status_code}: {response.text}")
            data = response.json()
            return data.get("response", "")
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

    def process_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        try:
            job_data = self.db.get_job_data(job_id)
            if not job_data:
                logger.warning(f"No job data for ID {job_id}")
                return None

            pdf_text = job_data.get("pdf_content", "")
            word_text = job_data.get("word_content", "")

            if not pdf_text or not word_text:
                logger.warning(f"Missing text for job {job_id}")
                return None

            prompt = self._generate_prompt(pdf_text, word_text)
            response = self._get_llm_response(prompt)

            print(f"[DEBUG] Raw LLM response for job {job_id}:\n{response[:3000]}")  # Only show first 500 chars

            json_data = get_json(response)
            if not json_data:
                logger.error(f"Invalid JSON for job {job_id}")
                self.db.update_job_status(
                    job_id,
                    status="failed",
                    debug_output={"error": "Invalid JSON", "raw_response": response}
                )
                return None

            try:
                inject_standardized_json_to_excel(json_data, self.template_path, self.output_path)
                logger.info(f"Successfully processed job {job_id}")
                return json_data
            except Exception as e:
                logger.error(f"Failed to write to Excel for job {job_id}: {e}")
                self.db.update_job_status(
                    job_id,
                    status="failed",
                    debug_output={"error": f"Excel save failed: {e}", "raw_response": response}
                )
                return None

        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            self.db.update_job_status(
                job_id,
                status="failed",
                debug_output={"error": f"Processing exception: {e}"}
            )
            return None


            inject_standardized_json_to_excel(json_data, self.template_path, self.output_path)
            logger.info(f"Processed job {job_id}")
            return json_data

        except Exception as e:
            logger.error(f"Error in job {job_id}: {e}")
            return None

    def process_all_pending_jobs(self):
        try:
            pending_jobs = self.db.get_pending_jobs()
            if not pending_jobs:
                logger.info("No pending jobs found")
                return

            logger.info(f"Found {len(pending_jobs)} jobs")
            for job in pending_jobs:
                job_id = job["id"]
                result = self.process_job(job_id)
                if result:
                    self.db.mark_job_completed(job_id)
                    logger.info(f"Completed job {job_id}")
                else:
                    self.db.mark_job_failed(job_id)
                    logger.error(f"Failed job {job_id}")
        except Exception as e:
            logger.error(f"Error processing jobs: {e}")
