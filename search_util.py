import re
import mysql.connector
from bs4 import BeautifulSoup

from db_config import get_connection
import html

def get_connection():
    return mysql.connector.connect(**db_config)

def highlight_terms(text, keyword):
    if not keyword:
        return html.escape(text).replace("\n", "<br>")

    # Escape the full text to avoid HTML injection
    escaped_text = html.escape(text)

    # Regex pattern to match keyword (case-insensitive)
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)

    # Highlight matched keyword only (no line breaks)
    highlighted = pattern.sub(
        lambda m: f"<mark style='background-color: yellow'>{m.group(0)}</mark>",
        escaped_text
    )

    return highlighted.replace("\n", "<br>")
    
def search_documents(file_id=None, property_name=None, keyword=None, owner_name=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT file_id, property_name, content, owner_name, first_page_image, second_page_image FROM updated_documents WHERE 1"
    params = []

    if file_id:
        query += " AND file_id = %s"
        params.append(file_id)
    if property_name:
        normalized = property_name.lower().replace(" ", "_").replace("_", " ")
        query += " AND LOWER(REPLACE(REPLACE(property_name, '_', ' '), '  ', ' ')) LIKE %s"
        params.append(f"%{normalized}%")
    if keyword:
        query += " AND content LIKE %s"
        params.append(f"%{keyword}%")
    if owner_name:
        query += " AND owner_name LIKE %s"
        params.append(f"%{owner_name}%")

    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()
    conn.close()

    # Highlight keyword
    for r in results:
        r["content"] = highlight_terms(r["content"], keyword)

    return results


from fuzzywuzzy import fuzz

def fuzzy_match_properties(user_input, threshold=70):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT file_id, property_name, content, owner_name, first_page_image, second_page_image FROM updated_documents")
    all_rows = cursor.fetchall()
    cursor.close()
    conn.close()

    matches = []
    for row in all_rows:
        score = fuzz.partial_ratio(user_input.lower(), row["property_name"].lower())
        if score >= threshold:
            matches.append((score, row))

    # ✅ Sort by score only (not full tuple)
    matches.sort(key=lambda x: x[0], reverse=True)

    return [match[1] for match in matches]


import spacy
nlp = spacy.load("en_core_web_sm")

def chunk_document(text, max_tokens=1000, overlap=200):
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents]

    chunks = []
    current, token_count = [], 0
    for sentence in sentences:
        tokens = sentence.split()
        if token_count + len(tokens) > max_tokens:
            chunks.append(" ".join(current))
            current = tokens[-overlap:]  # last few tokens
            token_count = len(current)
        else:
            current += tokens
            token_count += len(tokens)
    if current:
        chunks.append(" ".join(current))
    return chunks

def keyword_sql_match(question):
    from db_config import db_config
    import re
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    keywords = re.findall(r'\b\w+\b', question.lower())
    condition = " OR ".join([f"content LIKE '%{kw}%'" for kw in keywords])
    query = f"SELECT file_id, property_name, content FROM documents WHERE {condition} LIMIT 3"
    cursor.execute(query)
    return cursor.fetchall()

