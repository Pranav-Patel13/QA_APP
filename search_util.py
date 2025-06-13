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

def search_documents(file_id=None, property_name=None, keyword=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT file_id, property_name, content FROM updated_documents WHERE 1"
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
    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()
    conn.close()

    # ✅ Only filter content by keyword if file_id and property_name are not used
    if keyword and not file_id and not property_name:
        results = [r for r in results if keyword.lower() in r["content"].lower()]

    # Highlight keyword
    for r in results:
        r["content"] = highlight_terms(r["content"], keyword)

    return results

import re
from difflib import SequenceMatcher
import mysql.connector
from db_config import get_connection

def extract_keywords(text):
    stopwords = {"what", "is", "the", "of", "a", "an", "in", "for", "and", "how", "many", "list", "give", "tell", "me", "to"}
    return [word for word in re.findall(r'\b\w+\b', text.lower()) if word not in stopwords and len(word) > 2]

def fuzzy_match_properties(user_input):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT file_id, property_name, content FROM updated_documents")
    rows = cursor.fetchall()
    conn.close()

    user_input = user_input.lower()
    threshold = 0.6

    def similarity(a, b):
        return SequenceMatcher(None, a, b).ratio()

    matches = []
    for row in rows:
        score = similarity(user_input, row['property_name'].lower())
        if score >= threshold:
            matches.append(row)

    return matches

def keyword_sql_match(question):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    keywords = extract_keywords(question)
    if not keywords:
        return []
    condition = " OR ".join([f"content LIKE '%{kw}%'" for kw in keywords])
    cursor.execute(f"SELECT file_id, property_name, content FROM updated_documents WHERE {condition} LIMIT 5")
    return cursor.fetchall()

def chunk_document(text, max_tokens=1000, overlap=200):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+max_tokens])
        chunks.append(chunk)
        i += max_tokens - overlap
    return chunks


