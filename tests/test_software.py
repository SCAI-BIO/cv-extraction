# import pytest
# import sqlite3
# import json
# import os
# from app.Handler import (
#     initialize_db, add_job, update_job_status, get_jobs, get_next_pending_job
# )

# # Define a temporary database for testing
# TEST_DB_PATH = "tests/test_pdf_results.db"

# @pytest.fixture(scope="function")
# def setup_test_db():
#     """Fixture to set up a temporary test database."""
#     global DB_PATH
#     DB_PATH = TEST_DB_PATH  # Override DB path

#     # Ensure fresh database setup for each test
#     if os.path.exists(TEST_DB_PATH):
#         os.remove(TEST_DB_PATH)

#     initialize_db()
#     yield  # Test runs here

#     # Clean up after test
#     if os.path.exists(TEST_DB_PATH):
#         os.remove(TEST_DB_PATH)

# def test_add_job(setup_test_db):
#     """Test adding a new PDF processing job."""
#     job_id = add_job("test_pdf.pdf", "Extracted test content")
#     assert job_id > 0  # Ensure job ID is generated

#     jobs = get_jobs()
#     assert len(jobs) == 1
#     assert jobs[0][1] == "test_pdf.pdf"  # Check filename
#     assert jobs[0][4] == "pending"  # Check status

# def test_update_job_status(setup_test_db):
#     """Test updating job status and storing extracted data."""
#     job_id = add_job("test_pdf.pdf", "Extracted test content")
    
#     extracted_data = {"name": "John Doe", "email": "john@example.com"}
#     update_job_status(job_id, "done", extracted_data)

#     jobs = get_jobs()
#     assert jobs[0][4] == "done"  # Ensure status is updated

#     stored_data = json.loads(jobs[0][3])  # Convert string to JSON
#     assert stored_data["name"] == "John Doe"
#     assert stored_data["email"] == "john@example.com"

# def test_get_next_pending_job(setup_test_db):
#     """Test retrieving the next pending job (FIFO)."""
#     job1_id = add_job("test_pdf_1.pdf", "Content 1")
#     job2_id = add_job("test_pdf_2.pdf", "Content 2")

#     pending_job = get_next_pending_job()
#     assert pending_job[0] == job1_id  # First job should be processed first

#     update_job_status(job1_id, "done")

#     pending_job = get_next_pending_job()
#     assert pending_job[0] == job2_id  # Next pending job should be job2
