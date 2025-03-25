import sqlite3
import json
from datetime import datetime
import os

class DatabaseManager:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'cv_data.db')
        self.initialize_db()

    def initialize_db(self):
        """Creates the database table if it does not exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS cv_extractions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pdf_filename TEXT,
                        word_filename TEXT,
                        pdf_content TEXT,
                        word_content TEXT,
                        status TEXT DEFAULT 'pending',
                        excel_file_path TEXT,
                        debug_output TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                print("Database initialized successfully!")
        except sqlite3.Error as e:
            print(f"Error initializing database: {e}")

    def save_extraction(self, pdf_filename, word_filename, pdf_content, word_content, status="done", excel_file=None, debug_output=None):
        """Saves extraction results to the database (only Excel file path)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cv_extractions 
                (pdf_filename, word_filename, pdf_content, word_content, status, excel_file_path, debug_output, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pdf_filename,
                word_filename,
                pdf_content,
                word_content,
                status,
                excel_file,
                json.dumps(debug_output) if debug_output else None,
                datetime.now().isoformat()
            ))
            conn.commit()
            print("Extraction saved successfully!")




    def get_all_extractions(self):
            """Fetch all extractions from the database (returns only Excel file path)."""
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, pdf_filename, word_filename, status, excel_file_path, debug_output, timestamp FROM cv_extractions ORDER BY timestamp DESC')
                columns = [description[0] for description in cursor.description]
                results = []
                for row in cursor.fetchall():
                    result_dict = dict(zip(columns, row))

                    # Remove extracted_data handling completely
                    if "extracted_data" in result_dict:
                        del result_dict["extracted_data"]  # Remove this key entirely

                    results.append(result_dict)
                return results


    def add_job(self, pdf_filename, word_filename, pdf_content, word_content,status="pending"):
        """Adds a new job with both PDF and Word document data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO cv_extractions (pdf_filename, word_filename, pdf_content, word_content, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (pdf_filename, word_filename, pdf_content, word_content, status))
                conn.commit()
                job_id = cursor.lastrowid
                print(f"Job {job_id} added successfully!")
                return job_id
        except sqlite3.Error as e:
            print(f"Error adding job: {e}")
            return None





    def get_extraction_by_id(self, extraction_id):
        """Fetch a specific extraction by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM cv_extractions WHERE id = ?', (extraction_id,))
                result = cursor.fetchone()

                if result:
                    columns = [description[0] for description in cursor.description]
                    result_dict = dict(zip(columns, result))

                    # Fix: Only check extracted_data if it exists
                    if "extracted_data" in result_dict and result_dict["extracted_data"]:
                        result_dict["extracted_data"] = json.loads(result_dict["extracted_data"])
                    else:
                        result_dict["extracted_data"] = {}  # Safe fallback

                    return result_dict  # Return valid data
                
        except sqlite3.Error as e:
            print(f"Error retrieving extraction by ID: {e}")

        return None  # Ensure a return value


    def update_job_status(self, job_id, status, extracted_data=None, excel_file=None, debug_output=None):
        """Updates job status and optionally saves extracted data, Excel file path, and debug output."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                extracted_data_str = json.dumps(extracted_data) if extracted_data else "{}"
                debug_output_str = json.dumps(debug_output) if debug_output else "{}"

                cursor.execute("""
                    UPDATE cv_extractions 
                    SET status = ?, extracted_data = ?, excel_file_path = ?, debug_output = ?
                    WHERE id = ?
                """, (status, extracted_data_str, excel_file, debug_output_str, job_id))
                conn.commit()
                print(f"Job {job_id} updated to status: {status}!")
        except sqlite3.Error as e:
            print(f"Error updating job status: {e}")
    def get_pending_jobs(self):
            """Fetch all jobs that are still pending."""
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, pdf_filename, word_filename, pdf_content, word_content, status 
                        FROM cv_extractions WHERE status = 'pending'
                    """)
                    jobs = cursor.fetchall()

                    # Convert results to a list of dictionaries
                    jobs_list = []
                    for job in jobs:
                        jobs_list.append({
                            "id": job[0],
                            "pdf_filename": job[1],
                            "word_filename": job[2],
                            "pdf_content": job[3],
                            "word_content": job[4],
                            "status": job[5]
                        })

                    return jobs_list  # Returns a list of pending jobs

            except sqlite3.Error as e:
                print(f"Error fetching pending jobs: {e}")
                return []
    def get_pending_jobs(self):
        """Fetch all jobs that are still pending."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, pdf_filename, word_filename, pdf_content, word_content, status 
                FROM cv_extractions WHERE status = 'pending'
            """)
            jobs = cursor.fetchall()

            # Convert results to a list of dictionaries
            jobs_list = []
            for job in jobs:
                jobs_list.append({
                    "id": job[0],
                    "pdf_filename": job[1],
                    "word_filename": job[2],
                    "pdf_content": job[3],
                    "word_content": job[4],
                    "status": job[5]
                })

            return jobs_list  # Returns a list of pending jobs

        except sqlite3.Error as e:
            print(f"Error fetching pending jobs: {e}")
            return []
