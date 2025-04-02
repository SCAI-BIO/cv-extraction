import os
import time
import requests
import sys
import logging
from Utilities import check_english_proficiency


# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from database.db_manager import DatabaseManager
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
    db = DatabaseManager()
    print(f"Starting background job processor... Using model: {MODEL_NAME}")
    print(f"API endpoint: {OLLAMA_API_URL}")
    
    while True:
        try:
            # Get all pending jobs
            pending_jobs = db.get_pending_jobs()
            
            if pending_jobs:
                print(f"Found {len(pending_jobs)} pending jobs to process")
            
            for job in pending_jobs:
                job_id = job['id']
                pdf_filename = job['pdf_filename']
                word_filename = job['word_filename']
                
                print(f"Processing job {job_id}: {pdf_filename} + {word_filename}")
                
                # Update status to processing
                db.update_job_status(job_id, "processing")
                
                retries = 0
                while retries < MAX_RETRIES:
                    try:
                        # Generate prompt from uploaded content
                        prompt = generate_prompt(job['pdf_content'], job['word_content'])
                        
                        # Call Ollama API with the correct format
                        print(f"Sending request to LLM API (attempt {retries+1})...")
                        print(f"API URL: {OLLAMA_API_URL}")
                        print(f"Using model: {MODEL_NAME}")
                        
                        try:
                            # Ollama API format: http://localhost:11434/api/generate
                            # Check if we need to append /api/generate to the URL
                            api_url = OLLAMA_API_URL
                            if not api_url.endswith('/api/generate'):
                                if api_url.endswith('/'):
                                    api_url += 'api/generate'
                                else:
                                    api_url += '/api/generate'
                            
                            print(f"Final API URL: {api_url}")
                            
                            response = requests.post(
                                api_url,
                                json={
                                    "model": MODEL_NAME,
                                    "prompt": prompt,
                                    "stream": False
                                },
                                headers={"Content-Type": "application/json"},
                                timeout=3000  # Increase timeout to 5 minutes
                            )
                            
                            print(f"API Response Status: {response.status_code}")
                            
                            if response.status_code != 200:
                                print(f"API error: {response.status_code} - {response.text}")
                                raise Exception(f"API returned status code {response.status_code}: {response.text}")
                            
                            # Extract response from Ollama format
                            response_data = response.json()
                            print(f"Response data keys: {response_data.keys()}")
                            
                            response_text = response_data.get('response', '')
                            if not response_text:
                                print("Warning: Empty response from API")
                                print(f"Full response: {response_data}")
                                raise ValueError("Empty response from LLM API")
                            
                            print(f"Response text length: {len(response_text)}")
                            print(f"Response preview: {response_text[:200]}...")
                            
                        except requests.exceptions.RequestException as req_err:
                            print(f"Request error: {req_err}")
                            raise Exception(f"API request failed: {req_err}")
                        
                        # Process JSON response
                        json_data = get_json(response_text)
                        
                        if not json_data:
                            print("Failed to extract valid JSON from response")
                            print(f"Response text: {response_text[:500]}...")
                            raise ValueError("No valid JSON extracted from LLM response")
                        
                        # Save results to Excel
                        excel_filename = f"extraction_{job_id}_{pdf_filename.replace('.pdf', '')}.xlsx"
                        excel_path = os.path.join(extractions_dir, excel_filename)
                        save_json_to_excel(json_data, excel_path)
                        
                        # Update job as successful
                        db.update_job_status(
                            job_id, 
                            "done",
                            extracted_data=json_data,
                            excel_file=excel_path,
                            debug_output={
                                "model": MODEL_NAME,
                                "prompt_length": len(prompt),
                                "response_length": len(response_text)
                            }
                        )
                        
                        print(f"Job {job_id} completed successfully!")
                        break  # Exit retry loop on success
                    
                    except Exception as processing_error:
                        print(f"Error processing job {job_id} (attempt {retries+1}): {str(processing_error)}")
                        retries += 1
                        
                        if retries >= MAX_RETRIES:
                            # Update job as failed with error details
                            db.update_job_status(
                                job_id, 
                                "failed",
                                debug_output={"error": str(processing_error)}
                            )
                            print(f"Job {job_id} marked as failed after {MAX_RETRIES} attempts")
                        else:
                            # Wait before retrying
                            time.sleep(3)
            
            # Sleep between batches
            time.sleep(5)
                
        except Exception as e:
            print(f"Error in main processing loop: {e}")
            time.sleep(10)  # Longer sleep on main loop error
