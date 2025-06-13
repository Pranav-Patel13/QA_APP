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

    if keyword and not file_id and not property_name:
        results = [r for r in results if keyword.lower() in r["content"].lower()]

    for r in results:
        r["content"] = highlight_terms(r["content"], keyword)

    return results

def extract_keywords(text):
    stopwords = {"what", "is", "the", "of", "a", "an", "in", "for", "and", "how", "many", "list", "give", "tell", "me", "to"}
    return [word for word in re.findall(r'\b\w+\b', text.lower()) if word not in stopwords and len(word) > 2]

def fuzzy_match_properties(user_input, threshold=0.4):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT file_id, property_name, content FROM updated_documents")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"❌ DB error in fuzzy_match_properties: {e}")
        return []

    logging.info(f"🔍 Total rows fetched: {len(rows)}")

    user_input = user_input.lower()
    matches = []
    for row in rows:
        full_name = row["property_name"]
        prop_name = full_name.lower()
    
        # Use cleaned tokens instead of entire string
        user_input_clean = re.sub(r"[^a-zA-Z0-9\s]", "", user_input).strip()
        prop_name_clean = re.sub(r"[^a-zA-Z0-9\s]", "", prop_name).strip()
    
        score = SequenceMatcher(None, user_input_clean, prop_name_clean).ratio()
    
        print(f"🔍 Comparing '{user_input_clean}' vs '{prop_name_clean}' => Score: {score:.2f}")
        if score >= threshold:
            matches.append((score, row))

    matches.sort(key=lambda x: x[0], reverse=True)
    logging.info(f"✅ Matches found: {len(matches)}")
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
