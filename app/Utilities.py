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
        You are given two pieces of text: one from a PDF (CV) and one from a Word document (job application). They contain a person's application details for a PhD or research position in Machine Learning (ML), Deep Learning (DL), and Data Science.
        Give the extracted and inferred information in JSON format.

        #### Your Task:
        1. Read both texts:
           - Merge data if one document has fields the other does not.
           - If any field is missing from both, mark it as "Unknown" or "N/A".

        2. Extract these fields:
        first_name = extract_first_word(full_name)
        last_name = extract_last_word(full_name)
        contact_details = extract_contact_details(data)
        date_of_birth = extract_date_of_birth(data)
        gender = extract_gender(data)
        nationality = extract_nationality(data)
        fits_mobility_rules = check_mobility_rules(data)
        holds_master_degree = check_master_degree(data)
        holds_doctoral_degree = check_doctoral_degree(data)
        english_proficiency = check_english_proficiency(data)
        
        4. Final Output:
           ### Output
    - Return only a JSON output with:
      1. Extracted Fields (Name, Contact, Degrees, etc.).
      2. Research Experience detailed (list or summary).

        #### Example JSON (demonstration)

{{
"Name": {{
    "First Name": "John",
    "Last Name": "Doe"
}},
"Contact Information": {{
    "Email": "john.doe@example.com",
    "Phone Number": "+123456789"
}},
"Date of Birth": "1992-01-15",
"Gender": "Male",
"Nationality": "N/A",
"Highest Degree": "Master's in Data Science",
"University": {{
    "Bachelor's": "Example University (2012)",
    "Master's": "Data Science, Another University (2015)"
}},
"Research Experience": {{
    "Projects": ["Deep Learning for X", "Internship on NLP at Y"],
    "Publications": ["Co-author on a workshop paper at ICML 2020"]
}},
"Mobility Rule Compliance": "Yes",
"Holds/Will Hold a Master's Degree Before Deadline": "Yes",
"Holds a Doctoral Degree": "No",
"English Proficiency": "Yes",
"Eligibility Criteria Met": "Yes",
}}
}}

        ### Provided Texts

        PDF (CV) Content:
        {pdf_text}

        Word (Application) Content:
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