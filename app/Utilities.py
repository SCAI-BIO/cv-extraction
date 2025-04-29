import PyPDF2
import docx
import json
import pandas as pd
import re
import openpyxl
import os
import shutil



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
You are a data AI and you answer questions and return answers strictly in json format with no trailing commas and no marksdown based on the text provided for academic job applications return the main inforamtion about the applicant and answer these information just ignore his address
and mention what is asked from you and answer certain fields like ("Full-name","Date-of-birth","Gender": "Female",
  "Nationality","Holds-Master-Degree","E-Mail","Skills and competences", "Holds-Doctoral-Degree" , "Fits mobility rules?" , "English Proficiency?" and "Visa required?") with yes or no in json format.


You are given two raw texts from an applicant:
1. Their CV (PDF or word format)
2. Their job application (email or Word format)

Your task is to answer and extract information mentioned below and return it as **strict, flat JSON** — with no markdown, code blocks, or extra text and no trailling commas.
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
- **"Visa required?"** is set to `"Yes"` for all any other thing except the countries mentioned not left empty it is either yes or no.

5. **"Holds-Master-Degree"**: is set to yes If the applicant **explicitly states** they hold Master-Degree  set `"Holds-Master-Degree"` to `"Yes"`.
---

JSON Output Format:

Output should be in json format.
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
  "Research Experience": Alyehimer disease invistigation, Parkinson disease and lewi bodies
  
}}
---

Return your output **exactly like this** — no bullet points, no markdown, and no explanation.
**Double Check**:
If all fields that wanted are extracted especially Visa required, Holds Doctoral Degree and Fits mobility rules and English proficiency not any other language and answered as yes or no.

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

# def check_english_proficiency(text):
#     """
#     Checks if English proficiency criteria are met based on:
#     - IELTS score >= 6.5
#     - TOEFL score >= 90
#     - Mention of C1 or C2
#     """
#     text = text.lower()

#     # Check for C1 or C2
#     if "c1" in text or "c2" in text:
#         return "Yes"

#     # Check IELTS score
#     ielts_match = re.search(r"ielts[^0-9]*((6\.5|[7-9](?:\.5)?))", text)
#     if ielts_match:
#         try:
#             score = float(ielts_match.group(1))
#             if score >= 6.5:
#                 return "Yes"
#         except:
#             pass

#     # Check TOEFL score
#     toefl_match = re.search(r"toefl[^0-9]*([0-9]{2,3})", text)
#     if toefl_match:
#         try:
#             score = int(toefl_match.group(1))
#             if score >= 90:
#                 return "Yes"
#         except:
#             pass

#     return "Please fill this manually"


# def second_agent_rule_engine(llm_data: dict) -> dict:
#     """
#     Transforms LLM output (Agent 1) into validated, interpreted data.
#     defining the rules here.
#     """
#     #Raw fields
#     full_name = llm_data.get("Full-name", "").strip()
#     nationality = llm_data.get("Nationality", "").strip()
#     contact_country = llm_data.get("Country-Contact", "").strip().lower()
#     email = llm_data.get("E-Mail", "")
#     phone = llm_data.get("Phone-number", "")
#     dob = llm_data.get("Date-of-birth", "")
#     gender = llm_data.get("Gender", "")
#     languages = llm_data.get("Languages", "")

#     #Rule: Split full name
#     name_parts = full_name.split()
#     first_name = name_parts[0] if name_parts else ""
#     last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

#     # Rule: Mobility
#     if "german" in nationality.lower() or "germany" in contact_country:
#         mobility = "No"
#     else:
#         mobility = llm_data.get("Fits mobility rules?", "Unknown")

#     # Rule: Master + year
#     master = llm_data.get("Holds-Master-Degree", "Unknown")
#     year_master = llm_data.get("Year-of-graduation-Master", "Unknown")
#     try:
#         master_before_2025 = "Yes" if int(year_master) <= 2025 else "No"
#     except:
#         master_before_2025 = "Unknown"

#     # Rule: Doctoral Degree
#     doctoral = llm_data.get("Holds-Doctoral-Degree", "").strip().lower()
#     doctoral = doctoral.capitalize() if doctoral in ["yes", "no"] else "Please fill this manually"

#     # Rule: English Proficiency
#     english_proficiency = check_english_proficiency(languages)

#     # Rule: Eligibility
#     eligibility = "Yes" if (
#         mobility == "Yes" and master == "Yes" and master_before_2025 == "Yes"
#     ) else "No"

#     # Return final row
#     return {
#         "First Name": first_name,
#         "Last Name": last_name,
#         "Email": email,
#         "Phone Number": phone,
#         "Date of Birth": dob,
#         "Gender": gender,
#         "Nationality": nationality,
#         "Mobility Rule Met?": mobility,
#         "Holds Master Degree?": master,
#         "Master Degree Before 2025?": master_before_2025,
#         "Doctoral Degree?": doctoral,
#         "English Proficiency?": english_proficiency,
#         "Eligibility Criteria Met?": eligibility
#     }




# import openpyxl
# import os
# from datetime import datetime

# COLUMN_MAP = {
#     "First Name": 2,
#     "Last Name": 3,
#     "Contact Details": 4,
#     "Date of Birth": 5,
#     "Gender": 6,
#     "Fits mobility rules": 7,
#     "Nationality": 8,
#     "Holds/will hold a master degree or equivalent before October 2025?": 9,
#     "Holds doctoral degree?": 10,
#     "English proficiency": 11,
#     "Visa required?": 12
# }


# def build_refinement_prompt(initial_json, pdf_text, word_text):
#     return f"""
# You are an AI that edits and completes structured applicant data and return it in json format that what you need to focus on.

# You are given:
# 1. A partially filled JSON object (initial_json)
# 2. The full CV text
# 3. The job application letter text

# Your job is to:
# - Ensure the JSON includes these three fields:
#   1. "Research Experience"
#   2. "Holds-Doctoral-Degree"
#   3. "Visa required?"
# - If any are missing, you must add them.
# - If present but set to "Unknown", improve or complete the value based on the text.
# - Do not modify any other field.
# - Your output must be valid, clean JSON — with double quotes and commas where needed.
# - If this field is missing, empty, or marked as "Unknown", you MUST extract research-related details from the CV or application.
# - This includes things like thesis work, assistantships, internships, publications, or any mention of academic research.

# ---

# ### Field Logic:

# 1. *Research Experience*:
#    - Extract research-related content (e.g. "Worked on NLP thesis", "3 years research in AI,deep learning or machine learning").
#    - If none found, use: "Unknown".

# 2. *Holds-Doctoral-Degree*:
#    - Set to "Yes" if PhD, Doctorate, "Dr.", or dissertation is mentioned.
#    - Otherwise, set to "No".

# 3. *Visa required?*:
#    - Check "Nationality" field from initial JSON.
#    - If it's NOT one of these countries:
#      Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France,
#      Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands,
#      Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden
#      → then: "Yes"
#    - Else: "No"

# ---

# Rules:
# - Output must be valid JSON only.
# - Do not include markdown, explanations, or formatting.
# - Keep the original structure and field order.
# - Add missing fields as needed.

# {{

#   "Full-name": "Super Hero",
#   "Date-of-birth": "1987-09-19",
#   "Gender": "Female",
#   "Nationality": "Phantasia",
#   "Country-Contact": "Phantasia",
#   "E-Mail": "abc@gmail.com",
#   "Phone-number": "+11 12345678",
#   "Mobility-rule-compliance": "Yes",
#   "Bachelor University": "My University",
#   "Bachelor Degree title": "Computer Science",
#   "Year-of-graduation-Bachelor": 2010,
#   "Master University": "Another University",
#   "Master Degree title": "Master of the Universe",
#   "Year-of-graduation-Master": 2022,
#   "Skills": [
#     "TensorFlow",
#     "Keras",
#     "OpenCV",
#     "FSL",
#     "PsychoPy",
#     "CUDA"
#   ],
#   "Programming-languages": [
#     "Python",
#     "C++",
#     "R",
#     "MATLAB"
#   ],
#   "Languages": {{
#     "Funny Language": "Native/Fluent",
#     "English": "Fluent (C1/C2)"
#   }},
#   "Additional-Information": "N/A",
#   "Research Experience": "Conducted research in deep learning during Master's studies; published one paper on NLP.",
#   "Holds-Doctoral-Degree": "No",
#   "Visa required?": "Yes"
# }}

# ---

# Initial JSON:
# {initial_json}

# ---

# CV Text:
# {pdf_text}

# ---

# Job Application Text:
# {word_text}
# """




def normalize_text(text):
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r'\s+', ' ', text.lower().strip().replace("\n", " "))

def extract_combined_headers(ws, header_rows=[4, 5, 6]):
    headers = []
    max_col = ws.max_column
    for col in range(1, max_col + 1):
        combined = []
        for row in header_rows:
            val = ws.cell(row=row, column=col).value
            if val:
                combined.append(str(val).strip())
        headers.append(" ".join(combined).strip() if combined else None)
    return headers

def check_english_proficiency_from_text(text):
    if not text:
        return "Filled manually"

    text = str(text).lower()

    if "c1" in text or "c2" in text:
        return "Yes"

    patterns = {
        'ielts': 6.5,
        'toefl': 90,
        'pte': 61,
        'duolingo': 110,
        'cambridge': 180,
        'cae': 180
    }

    for exam, threshold in patterns.items():
        match = re.search(rf"{exam}[^0-9]*([\d\.]+)", text)
        if match:
            try:
                score = float(match.group(1))
                if score >= threshold:
                    return "Yes"
            except:
                pass

    return "Filled manually"

def detect_master_degree(flat_json):
    for raw_key, raw_value in flat_json.items():
        key = normalize_text(raw_key)
        value = str(raw_value).strip().lower()

        # First check: if value is "yes" or "true" (any casing)
        if value in ["yes", "true", "1"]:
            return "Yes"

        # Second check: if key has "degree" and value has "master"
        if "degree" in key and "master" in value:
            return "Yes"

    # If neither found
    return "Filled manually"

def detect_doctoral_degree(flat_json):
    for key, value in flat_json.items():
        key_norm = normalize_text(key)
        value_str = str(value).strip().lower()

        if "phd" in key_norm or "phd" in value_str or "doctor" in value_str:
            if value_str in ["yes", "true", "1"]:
                return "Yes"
    return "No"

# List of European countries
european_countries = [
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech republic",
    "denmark", "estonia", "finland", "france", "germany", "greece",
    "hungary", "ireland", "italy", "latvia", "lithuania", "luxembourg",
    "malta", "netherlands", "poland", "portugal", "romania", "slovakia",
    "slovenia", "spain", "sweden", "norway", "switzerland", "iceland",
    "liechtenstein"
]

def detect_visa_required(flat_json):
    visa_key = "visa required"
    nationality_key = "nationality"

    if visa_key in flat_json:
        value = str(flat_json[visa_key]).strip().lower()
        if value in ["yes", "true", "1"]:
            return "Yes"
        elif value in ["no", "false", "0"]:
            return "No"
        else:
            return "Filled manually"
    
    nationality = flat_json.get(nationality_key, "").lower()
    if any(country in nationality for country in european_countries):
        return "No"
    else:
        return "Yes"

def split_full_name(full_name):
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:]) if len(parts) > 1 else ""

# --- Field mapping ---

field_map = {
    "first name": ["first name", "full-name", "full name", "name"],
    "last name": ["last name", "surname"],
    "gender": ["gender", "sex"],
    "date of birth": ["date-of-birth", "dob", "birthdate"],
    "nationality": ["nationality", "country-contact", "country", "country of origin"],
    "contact details (e.g. email)": ["email", "e-mail", "contact_email"],
    "phone number": ["phone_number", "phone", "phone-number", "mobile", "contact number"],
    "fits mobility rules?": ["mobility rule compliance", "mobility-rule-compliance", "fits mobility rules", "mobility rules"],
    "holds doctoral degree?": ["holds doctoral degree", "holds-doctoral-degree", "has phd", "phd", "doctorate"],
    "visa required?": ["visa required", "visa_required", "requires visa", "needs visa"],
    "english proficiency?": ["english proficiency", "language level", "english level", "spoken english"],
    "skills and competencies (max 5 points)": ["skills", "technical skills", "competencies", "frameworks", "tools", "programming-languages"],
    "holds/will hold a master degree or equivalent before october 2025?": ["master degree", "master-degree", "degree title", "holds-master-degree"]
}

# --- Excel Injection Function ---

def inject_standardized_json_to_excel(json_data, template_path, output_path):
    if not os.path.exists(output_path):
        shutil.copy(template_path, output_path)

    wb = openpyxl.load_workbook(output_path)
    ws = wb.active

    headers = extract_combined_headers(ws)
    normalized_headers = [normalize_text(h) if h else "" for h in headers]

    flat_json = {}
    for k, v in json_data.items():
        if isinstance(v, dict):
            for subk, subv in v.items():
                flat_json[f"{normalize_text(k)}_{normalize_text(subk)}"] = subv
        else:
            flat_json[normalize_text(k)] = v

    full_name = json_data.get("Full-name", "") or json_data.get("Name", "")
    first_name, last_name = split_full_name(full_name)

    language_info = json_data.get("Languages", "")
    if isinstance(language_info, dict):
        language_info = " ".join(language_info.values())

    row = 7
    while ws.cell(row=row, column=1).value:
        row += 1

    for col_idx, header in enumerate(headers, 1):
        if not header:
            ws.cell(row=row, column=col_idx, value="Filled manually")
            continue

        norm_header = normalize_text(header)
        value = "Filled manually"

        for expected, aliases in field_map.items():
            expected_norm = normalize_text(expected)
            if expected_norm in norm_header:
                for alias in aliases:
                    alias = normalize_text(alias)
                    for flat_key, flat_val in flat_json.items():
                        if alias in flat_key:
                            value = flat_val
                            break
                    if value != "Filled manually":
                        break
                break

        if "first name" in norm_header:
            value = first_name
        elif "last name" in norm_header:
            value = last_name
        elif "english proficiency?" in norm_header:
            value = check_english_proficiency_from_text(language_info)
        elif "holds/will hold a master degree" in norm_header:
            value = detect_master_degree(flat_json)
        elif "holds doctoral degree?" in norm_header:
            value = detect_doctoral_degree(flat_json)
        elif "visa required?" in norm_header:
            value = detect_visa_required(flat_json)

        if isinstance(value, list):
            value = "; ".join(map(str, value))

        ws.cell(row=row, column=col_idx, value=value)

    wb.save(output_path)
    print("Data successfully written to Excel.")