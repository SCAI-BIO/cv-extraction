import PyPDF2
import docx
import json
import pandas as pd
import re
from pandas import json_normalize

def extract_text_from_pdf(uploaded_pdf):
    """Extracts text from a PDF file."""
    pdf_reader = PyPDF2.PdfReader(uploaded_pdf)
    text = "\n".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
    return text

def extract_text_from_word(uploaded_word):
    """Extracts text from a Word document."""
    doc = docx.Document(uploaded_word)
    text = "\n".join([para.text for para in doc.paragraphs if para.text])
    return text

def generate_prompt(pdf_text, word_text):
    return f"""
You are a data AI and you answer questions based on the text provided for academic job applications return the answer for these information ignore his address
just mention what is asked from you


You are given two raw texts from an applicant:
1. Their CV (PDF or word format)
2. Their job application (email or Word format)

Your task is to extract **specific information** and return it as **strict, flat JSON** — with no markdown, code blocks, or extra text and no trailling commas.
Apply the following extraction rules:

1. **Mobility Rule**:
   - Extract it from the application form which states it as either Yes or No.

2. **English Proficiency**:
   - This must reflect whether the candidate likely meets the programs minimum language requirement.
   - Set `"English Proficiency"` to `"Yes"` if **any** of the following is mentioned:
     - An **IELTS** score of **6.5 or above** (e.g., "IELTS 7", "IELTS 8.0")
     - A **TOEFL** score of **90 or above** (e.g., "TOEFL 94", "TOEFL iBT 100")
     - A **language level of C1 or C2** in English.

3. **Doctoral Degree**:
   - If the applicant **explicitly states** they hold a PhD or doctorate, set `"Holds-Doctoral-Degree"` to `"Yes"`.
   - If it is not mentioned, respond with "No".

4. **Visa Requirement**:
   - - **"Visa required?"** is set to `"No"` if the nationality is from any of the following EU countries:
  Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden.
- **"Visa required?"** is set to `"Yes"` for all any other thing except the countries mentioned.


---

JSON Output Format:

The output **must** contain only the following fields:

- "Full-name"
- "Date-of-birth"
- "Gender"
- "Nationality"
- "Country-Contact"
- "E-Mail"
- "Phone-number"
- "Holds-Master-Degree"
- "Year-of-graduation-Master"
- "Languages"
- "Skills and competences"
- "Research Experience"
- "Holds-Doctoral-Degree"
- "Fits mobility rules?"
- "English Proficiency?"
- "Visa required?"

All values must be plain strings. If a value is not mentioned or unclear, use **"Unknown"**.

---

Example Output Format (use exactly this structure):

{{
  "Full-name": "Jane Doe",
  "Date-of-birth": "1993-04-21",
  "Gender": "Female",
  "Nationality": "Spanish",
  "Country-Contact": "Spain",
  "E-Mail": "jane.doe@example.com",
  "Phone-number": "+34 123 456 789",
  "Holds-Master-Degree": "Yes",
  "Year-of-graduation-Master": "2020",
  "English profiency": "English (C1),
  "Skills and competences": "Strong communication, excellent analytical skills",
  "Holds-Doctoral-Degree": "No",
  "Fits mobility rules?": "Yes",
  "English proficiency?": "Yes",
  "Research Experience"
  
}}
---

Return your output **exactly like this** — no bullet points, no markdown, and no explanation.
**Double Check**:
If all fields that wanted are extracted especially Visa required, Holds Doctoral Degree and Fits mobility rules and English proficiency not any other language 

---

CV Text:
{pdf_text}

Job Application Text:
{word_text}
"""


def fix_trailing_commas(json_text):
    """Removes trailing commas before } or ] to fix JSON format."""
    return re.sub(r',\s*([\]}])', r'\1', json_text)

def fix_unclosed_brackets(json_text):
    """Ensures all opening { or [ have matching closing } or ]."""
    open_curly, close_curly = json_text.count('{'), json_text.count('}')
    open_square, close_square = json_text.count('['), json_text.count(']')

    json_text += '}' * (open_curly - close_curly)
    json_text += ']' * (open_square - close_square)
    
    return json_text

def get_json(response_text):
    """Extracts and fixes JSON before parsing."""
    # First try to find JSON inside code blocks
    json_match = re.search(r'```(?:json)?\s*(\{(?:[^{}]*|\{.*?\})*\})\s*```', response_text, re.DOTALL)

    if not json_match:
        # Fallback to finding raw JSON
        json_match = re.search(r'\{(?:[^{}]*|\{.*?\})*\}', response_text, re.DOTALL)

    if json_match:
        json_text = json_match.group(1) if '```' in json_match.group(0) else json_match.group(0)

        #Apply fixes before parsing
        json_text = fix_trailing_commas(json_text)
        json_text = fix_unclosed_brackets(json_text)

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            print(f"Problematic snippet: {json_text[max(0, e.pos - 40): min(len(json_text), e.pos + 40)]}")
            return None
    else:
        print("No valid JSON block found in the response.")
        return None


def flatten_json(nested_json, parent_key='', sep='_'):
    """
    Recursively flattens a nested JSON structure.

    Args:
        nested_json (dict or list): The JSON data.
        parent_key (str): Key prefix for nested fields.
        sep (str): Separator for flattened keys.

    Returns:
        dict: Flattened dictionary.
    """
    flattened_dict = {}

    def recurse(data, prefix=''):
        if isinstance(data, dict):
            for key, value in data.items():
                new_key = f"{prefix}{sep}{key}" if prefix else key
                recurse(value, new_key)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_key = f"{prefix}{sep}{i}" if prefix else str(i)
                recurse(item, new_key)
        else:
            flattened_dict[prefix] = data

    recurse(nested_json)
    return flattened_dict

def save_json_to_excel(data, filename="extracted_data.xlsx"):
    """
    Saves structured JSON data into an Excel file with multiple sheets.

    Args:
        data (dict): Extracted JSON data.
        filename (str): Output Excel filename.

    Returns:
        str: Filename of the saved Excel file.
    """
    if not data:
        print("No data to save.")
        return None

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        # Flatten entire JSON for main sheet
        flattened_data = flatten_json(data)
        df_main = pd.DataFrame([flattened_data])
        df_main.to_excel(writer, sheet_name="Main Data", index=False)

        # Handle lists & nested tables dynamically
        for key, value in data.items():
            if isinstance(value, list):  # If a list, create a new sheet
                df_list = pd.DataFrame(value)
                df_list.to_excel(writer, sheet_name=key[:30], index=False)  # Limit sheet name to 30 chars

    return filename


import re

def check_english_proficiency(text):
    """
    Checks if English proficiency criteria are met based on:
    - IELTS score >= 6.5
    - TOEFL score >= 90
    - Mention of C1 or C2
    """
    text = text.lower()

    # Check for C1 or C2
    if "c1" in text or "c2" in text:
        return "Yes"

    # Check IELTS score
    ielts_match = re.search(r"ielts[^0-9]*((6\.5|[7-9](?:\.5)?))", text)
    if ielts_match:
        try:
            score = float(ielts_match.group(1))
            if score >= 6.5:
                return "Yes"
        except:
            pass

    # Check TOEFL score
    toefl_match = re.search(r"toefl[^0-9]*([0-9]{2,3})", text)
    if toefl_match:
        try:
            score = int(toefl_match.group(1))
            if score >= 90:
                return "Yes"
        except:
            pass

    return "Please fill this manually"


def second_agent_rule_engine(llm_data: dict) -> dict:
    """
    Transforms LLM output (Agent 1) into validated, interpreted data.
    defining the rules here.
    """
    #Raw fields
    full_name = llm_data.get("Full-name", "").strip()
    nationality = llm_data.get("Nationality", "").strip()
    contact_country = llm_data.get("Country-Contact", "").strip().lower()
    email = llm_data.get("E-Mail", "")
    phone = llm_data.get("Phone-number", "")
    dob = llm_data.get("Date-of-birth", "")
    gender = llm_data.get("Gender", "")
    languages = llm_data.get("Languages", "")

    #Rule: Split full name
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    # Rule: Mobility
    if "german" in nationality.lower() or "germany" in contact_country:
        mobility = "No"
    else:
        mobility = llm_data.get("Fits mobility rules?", "Unknown")

    # Rule: Master + year
    master = llm_data.get("Holds-Master-Degree", "Unknown")
    year_master = llm_data.get("Year-of-graduation-Master", "Unknown")
    try:
        master_before_2025 = "Yes" if int(year_master) <= 2025 else "No"
    except:
        master_before_2025 = "Unknown"

    # Rule: Doctoral Degree
    doctoral = llm_data.get("Holds-Doctoral-Degree", "").strip().lower()
    doctoral = doctoral.capitalize() if doctoral in ["yes", "no"] else "Please fill this manually"

    # Rule: English Proficiency
    english_proficiency = check_english_proficiency(languages)

    # Rule: Eligibility
    eligibility = "Yes" if (
        mobility == "Yes" and master == "Yes" and master_before_2025 == "Yes"
    ) else "No"

    # Return final row
    return {
        "First Name": first_name,
        "Last Name": last_name,
        "Email": email,
        "Phone Number": phone,
        "Date of Birth": dob,
        "Gender": gender,
        "Nationality": nationality,
        "Mobility Rule Met?": mobility,
        "Holds Master Degree?": master,
        "Master Degree Before 2025?": master_before_2025,
        "Doctoral Degree?": doctoral,
        "English Proficiency?": english_proficiency,
        "Eligibility Criteria Met?": eligibility
    }




import openpyxl
import os
from datetime import datetime

COLUMN_MAP = {
    "First Name": 2,
    "Last Name": 3,
    "Contact Details": 4,
    "Date of Birth": 5,
    "Gender": 6,
    "Fits mobility rules": 7,
    "Nationality": 8,
    "Holds/will hold a master degree or equivalent before October 2025?": 9,
    "Holds doctoral degree?": 10,
    "English proficiency": 11,
    "Visa required?": 12
}

def generate_applicant_id(json_data):
    last_name = json_data.get("Last Name", "unknown").strip().lower().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return f"{last_name}_{timestamp}"

def append_to_master_excel(json_data, master_path, start_row=7):
    if not os.path.exists(master_path):
        raise FileNotFoundError(f"Master file not found at {master_path}")

    wb = openpyxl.load_workbook(master_path)
    ws = wb.active

    # Find next available row
    row = start_row
    while ws.cell(row=row, column=1).value:
        row += 1

    # Generate and write applicant ID in column 1
    applicant_id = generate_applicant_id(json_data)
    ws.cell(row=row, column=1, value=applicant_id)

    # Write remaining mapped fields
    for field, col in COLUMN_MAP.items():
        value = json_data.get(field, "Fill the field manually")
        ws.cell(row=row, column=col, value=value)

    wb.save(master_path)


def build_refinement_prompt(initial_json, pdf_text, word_text):
    return f"""
You are an AI that edits and completes structured applicant data in JSON format.

You are given:
1. A partially filled JSON object (initial_json)
2. The full CV text
3. The job application letter text

Your job is to:
- Ensure the JSON includes these three fields:
  1. "Research Experience"
  2. "Holds-Doctoral-Degree"
  3. "Visa required?"
- If any are missing, you must add them.
- If present but set to "Unknown", improve or complete the value based on the text.
- Do not modify any other field.
- Your output must be valid, clean JSON — with double quotes and commas where needed.
- If this field is missing, empty, or marked as "Unknown", you MUST extract research-related details from the CV or application.
- This includes things like thesis work, assistantships, internships, publications, or any mention of academic research.

---

### Field Logic:

1. *Research Experience*:
   - Extract research-related content (e.g. "Worked on NLP thesis", "3 years research in AI,deep learning or machine learning").
   - If none found, use: "Unknown".

2. *Holds-Doctoral-Degree*:
   - Set to "Yes" if PhD, Doctorate, "Dr.", or dissertation is mentioned.
   - Otherwise, set to "No".

3. *Visa required?*:
   - Check "Nationality" field from initial JSON.
   - If it's NOT one of these countries:
     Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France,
     Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands,
     Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden
     → then: "Yes"
   - Else: "No"

---

Rules:
- Output must be valid JSON only.
- Do not include markdown, explanations, or formatting.
- Keep the original structure and field order.
- Add missing fields as needed.

{{
  "Research Experience": "Conducted research in deep learning during Master's studies; published one paper on NLP.",
  "Holds-Doctoral-Degree": "No",
  "Visa required?": "Yes"
}}

---

Initial JSON:
{initial_json}

---

CV Text:
{pdf_text}

---

Job Application Text:
{word_text}
"""