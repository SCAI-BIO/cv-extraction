# import json
# import re
# import pandas as pd
# from pandas import json_normalize

# def get_json(response_text):
#     """Extracts and fixes JSON before parsing.
    
#     Args:
#         response_text (str): Text containing JSON data
        
#     Returns:
#         dict: Parsed JSON data or None if extraction/parsing fails
#     """
#     json_match = re.search(r'```(?:json)?\s*(\{(?:[^{}]*|\{.*?\})*\})\s*```', response_text, re.DOTALL)

#     if not json_match:
#         # Fallback to finding raw JSON
#         json_match = re.search(r'\{(?:[^{}]*|\{.*?\})*\}', response_text, re.DOTALL)

#     if json_match:
#         json_text = json_match.group(1) if '```' in json_match.group(0) else json_match.group(0)

#         ##print("\nExtracted JSON Before Fixing:\n", json_text)  # Debugging Step

#         # Remove any incorrectly escaped quotes
#         json_text = json_text.replace('\\"', '"')

#         # Fix missing commas between objects
#         json_text = re.sub(r'}\s*{', '}, {', json_text)

#         # Fix missing commas before list items
#         json_text = re.sub(r'(?<=\})\s*\n\s*"Skills"', ',\n  "Skills"', json_text)

#         # Fix incorrectly formatted Skills array
#         json_text = re.sub(r'"\s*Frameworks"\s*:', '"Frameworks: "', json_text)

#         try:
#             parsed_json = json.loads(json_text)
#             return parsed_json
#         except json.JSONDecodeError as e:
#             print("Error decoding JSON at position", e.pos)
#             print("Error message:", str(e))
#             context_start = max(0, e.pos - 40)
#             context_end = min(len(json_text), e.pos + 40)
#             print("Problematic text snippet:", json_text[context_start:context_end])
#             return None
#     else:
#         print("No valid JSON block found in the response.")
#         return None




# x = '''<think>
# I need to extract structured information from two sources: a CV (PDF) and a job application (Word document). My goal is to merge both documents into a **consistent JSON format**.

# First, I will check for **the full name**. The job application explicitly states "John Doe," while the CV only mentions "J. Doe." The full name should be "John Doe," with "John" as the first name and "Doe" as the last name.

# Next, **contact details** should be extracted. The job application includes an email (johndoe@example.com) and a phone number (+44 123 456 7890). The CV provides a LinkedIn link, which is optional but can be included.

# For **date of birth**, the job application states "15/06/1990," so I will convert it to **ISO format: "1990-06-15".** Gender is listed as "Male" in the job application, and nationality is given as "British."

# Regarding **education**, the CV contains details of a "Master of Science in Artificial Intelligence" from "University of London" (Graduated in 2020). The job application confirms a **Bachelor’s Degree in Computer Science** from "Oxford University" (Graduated in 2017). These will be recorded as separate entries under "Education."

# For **research experience**, the CV provides details on two AI-related research projects:
# 1. **"AI in Healthcare"** - Developed ML models for disease detection.
# 2. **"NLP for Business Insights"** - Built a text classification model for financial data.

# The **skills** section should include:
# - **Frameworks:** TensorFlow, PyTorch, OpenCV
# - **Programming Languages:** Python, Java, C++

# For **English proficiency**, the job application lists **"Fluent (C2)"** under language skills. 

# The eligibility check confirms that **all required fields are provided, and mobility rules are met**.

# Now, I will structure the extracted details into a JSON format.
# </think>

# ```json
# {
#   "Full Name": {
#     "First Name": "John",
#     "Last Name": "Doe"
#   },
#   "Contact Details": {
#     "Email": "johndoe@example.com",
#     "Phone Number": "+44 123 456 7890",
#     "LinkedIn": "linkedin.com/in/johndoe"
#   },
#   "Date of Birth": "1990-06-15",
#   "Gender": "Male",
#   "Nationality": "British",
#   "Mobility Rule Compliance": "Yes",
#   "Education": {
#     "Bachelor's Degree": {
#       "University Name": "Oxford University",
#       "Country": "United Kingdom",
#       "Degree Title": "Computer Science",
#       "Year of Graduation": "2017"
#     },
#     "Master's Degree": {
#       "University Name": "University of London",
#       "Country": "United Kingdom",
#       "Degree Title": "Artificial Intelligence",
#       "Year of Graduation": "2020"
#     }
#   },
#   "Skills": [
#     "Frameworks: TensorFlow, PyTorch, OpenCV",
#     "Programming languages: Python, Java, C++"
#   ],
#   "Languages": {
#     "English": "Fluent (C2)"
#   },
#   "Additional Qualifications": [
#     "Experience in Deep Learning and NLP",
#     "Published research on AI in Healthcare"
#   ],
#   "Research Experience": {
#     "Projects": [
#       "AI in Healthcare: Developed ML models for disease detection.",
#       "NLP for Business Insights: Built a text classification model for financial data."
#     ],
#     "Publications": [
#       "AI for Healthcare, published in IEEE Journal."
#     ]
#   },
#   "English Proficiency": "Fluent",
#   "Eligibility Criteria Met": "Yes"
# }

# ```

# ### Notes:
# - The JSON structure includes all the relevant information extracted from both documents.
# - For fields that are not explicitly mentioned or are unclear, they have been marked as "Unknown" or left blank where appropriate.
# - Dates and formats have been standardized based on the provided example.'''

# print(get_json(x))




# def flatten_json(nested_json, parent_key='', sep='_'):
#     """
#     Recursively flattens a nested JSON structure.

#     Args:
#         nested_json (dict or list): The JSON data.
#         parent_key (str): Key prefix for nested fields.
#         sep (str): Separator for flattened keys.

#     Returns:
#         dict: Flattened dictionary.
#     """
#     flattened_dict = {}

#     def recurse(data, prefix=''):
#         if isinstance(data, dict):
#             for key, value in data.items():
#                 new_key = f"{prefix}{sep}{key}" if prefix else key
#                 recurse(value, new_key)
#         elif isinstance(data, list):
#             for i, item in enumerate(data):
#                 new_key = f"{prefix}{sep}{i}" if prefix else str(i)
#                 recurse(item, new_key)
#         else:
#             flattened_dict[prefix] = data

#     recurse(nested_json)
#     return flattened_dict

# def save_json_to_excel(data, filename="extracted_data.xlsx"):
#     """
#     Saves structured JSON data into an Excel file with multiple sheets.

#     Args:
#         data (dict): Extracted JSON data.
#         filename (str): Output Excel filename.

#     Returns:
#         str: Filename of the saved Excel file.
#     """
#     if not data:
#         print("No data to save.")
#         return None

#     with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        
#         # Flatten entire JSON
#         flattened_data = flatten_json(data)
#         df_main = pd.DataFrame([flattened_data])
#         df_main.to_excel(writer, sheet_name="Main Data", index=False)

#         # Handle lists & nested tables dynamically
#         for key, value in data.items():
#             if isinstance(value, list):  # If a list, create a new sheet
#                 df_list = pd.DataFrame(value)
#                 df_list.to_excel(writer, sheet_name=key[:30], index=False)  # Limit sheet name to 30 chars
        
#             elif isinstance(value, dict):  # If a nested dict, normalize it
#                 df_dict = pd.DataFrame([flatten_json(value)])
#                 df_dict.to_excel(writer, sheet_name=key[:30], index=False)

#     print(f"JSON successfully saved to {filename}")
#     return filename


# # Extract JSON from response
# parsed_json = get_json(x)

# # Save JSON to Excel
# excel_filename = save_json_to_excel(parsed_json, "cv_extracted_data.xlsx")

# print(f"Excel file saved: {excel_filename}")



from database.db_manager import DatabaseManager

# Initialize the database manager
db = DatabaseManager()

# Step 1: Add a job
job_id = db.add_job("test_pdf.pdf", "test_doc.docx", "PDF Content", "Word Content")
print(f"✅ Job {job_id} added successfully!")

# Step 2: Fetch all extractions
extractions = db.get_all_extractions()
if extractions:
    print(f"📜 Found {len(extractions)} extractions!")
    for ext in extractions:
        print(f"📝 ID: {ext['id']}, Status: {ext['status']}, PDF: {ext['pdf_filename']}")
else:
    print("⚠️ No extractions found!")

# Step 3: Update job status
db.update_job_status(job_id, "done", {"name": "John Doe"}, "test_results.xlsx", {"debug": "Debug info"})
print(f"✅ Job {job_id} updated to 'done'!")

# Step 4: Fetch updated job
updated_job = db.get_extraction_by_id(job_id)
if updated_job:
    print(f"📌 Updated Job ID {job_id}: {updated_job['status']}")
else:
    print("⚠️ Job not found!")
