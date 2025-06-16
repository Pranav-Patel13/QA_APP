import re
import html
import logging
from difflib import SequenceMatcher
import mysql.connector
from db_config import get_connection

logging.basicConfig(level=logging.INFO)

def highlight_terms(text, keyword):
    if not keyword:
        return html.escape(text).replace("\n", "<br>")
    escaped_text = html.escape(text)
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
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

def extract_keywords(text):
    stopwords = {"what", "is", "the", "of", "a", "an", "in", "for", "and", "how", "many", "list", "give", "tell", "me", "to"}
    return [word for word in re.findall(r'\b\w+\b', text.lower()) if word not in stopwords and len(word) > 2]

from fuzzywuzzy import fuzz
import re

def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower().strip()

def fuzzy_match_properties(user_input, threshold=65):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT file_id, property_name, content FROM updated_documents")
    all_rows = cursor.fetchall()
    cursor.close()
    conn.close()

    matches = []

    cleaned_input = clean_text(user_input)
    input_tokens = set(cleaned_input.split())

    for row in all_rows:
        prop_name = row["property_name"]
        cleaned_name = clean_text(prop_name)
        name_tokens = set(cleaned_name.split())

        # Token overlap score
        token_overlap = len(input_tokens.intersection(name_tokens)) / max(len(input_tokens), 1)

        # Fuzzy score (backup)
        fuzzy_score = fuzz.partial_ratio(cleaned_input, cleaned_name)

        # Final score: balance overlap and fuzzy
        final_score = int((token_overlap * 100 + fuzzy_score) / 2)

        if final_score >= threshold:
            matches.append((final_score, row))

    matches.sort(key=lambda x: x[0], reverse=True)
    return [match[1] for match in matches]


def keyword_sql_match(question):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        keywords = extract_keywords(question)
        if not keywords:
            return []
        condition = " OR ".join([f"content LIKE '%{kw}%'" for kw in keywords])
        cursor.execute(f"SELECT file_id, property_name, content FROM updated_documents WHERE {condition} LIMIT 5")
        return cursor.fetchall()
    except Exception as e:
        logging.error(f"❌ DB error in keyword_sql_match: {e}")
        return []

def chunk_document(text, max_tokens=1000, overlap=200):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+max_tokens])
        chunks.append(chunk)
        i += max_tokens - overlap
    return chunks
