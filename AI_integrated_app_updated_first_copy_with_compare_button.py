import streamlit as st
import html
import re
import time
from bs4 import BeautifulSoup
from search_util import chunk_document, fuzzy_match_properties, keyword_sql_match
from llm_util import query_ollama  # ✅ Import only the remote LLM call
import pandas as pd

# 🧽 Document cleaning for UI
def clean_and_highlight(text, keyword):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    raw_text = soup.get_text(separator="\n")
    lines = raw_text.splitlines()

    formatted_lines = []
    inside_table = False
    text_buffer = ""

    def highlight(text, keyword):
        if not keyword:
            return html.escape(text)
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        return pattern.sub(
            lambda m: f"<mark style='background-color: yellow; color: black'>{m.group(0)}</mark>",
            html.escape(text)
        )

    def flush_buffer():
        nonlocal text_buffer
        if text_buffer:
            formatted_lines.append(f"<p>{highlight(text_buffer.strip(), keyword)}</p>")
            text_buffer = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_buffer()
            formatted_lines.append("<br>")
            continue
        if stripped.startswith("===") and stripped.endswith("==="):
            flush_buffer()
            title = stripped.strip("=").strip()
            formatted_lines.append(f"<h4 style='color:#4A90E2'>{html.escape(title)}</h4>")
            continue
        if stripped == "--- TABLE ---":
            flush_buffer()
            inside_table = True
            formatted_lines.append("<table style='border-collapse:collapse; width:100%; margin-top:10px'>")
            continue
        if stripped == "--- END TABLE ---":
            inside_table = False
            formatted_lines.append("</table><br>")
            continue
        if inside_table:
            flush_buffer()
            cells = [
                f"<td style='border:1px solid #ccc; padding:6px'>{highlight(c.strip(), keyword)}</td>"
                for c in line.split("|")
            ]
            formatted_lines.append(f"<tr>{''.join(cells)}</tr>")
        else:
            if text_buffer and not text_buffer.endswith((".", ":", "?", "!", ")", "’", "”", "\"")):
                text_buffer += " " + stripped
            else:
                flush_buffer()
                text_buffer = stripped

    flush_buffer()
    return "\n".join(formatted_lines)

# 🔍 Extract keywords from user question
def extract_keywords_from_question(question, stopwords=None):
    if stopwords is None:
        stopwords = {
            "what", "is", "the", "of", "a", "an", "in", "for", "and", "how", "many",
            "list", "give", "tell", "me", "to", "find", "show", "details", "number"
        }
    tokens = re.findall(r'\b\w+\b', question.lower())
    return [token for token in tokens if token not in stopwords and len(token) > 2]

# 🧠 Basic fallback logic if LLM fails
def dynamic_regex_fallback(doc_text: str, user_question: str) -> str:
    keywords = extract_keywords_from_question(user_question)
    if not keywords:
        return "Not mentioned."
    lines = doc_text.splitlines()
    for line in lines:
        line_lower = line.lower()
        if all(k in line_lower for k in keywords):
            match = re.search(r"[:|]\s*(\d{1,3}\s*\w+)", line)
            if match:
                return match.group(1).strip()
    keyword_pattern = r".*?".join(map(re.escape, keywords))
    value_pattern = rf"{keyword_pattern}.*?[:|\-]?\s*([\w\s.,/-]+)"
    match = re.search(value_pattern, doc_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Not mentioned."

def simulate_typing(text, delay=0.04):
    output = st.empty()
    typed = ""
    for char in text:
        typed += char
        output.markdown(typed + "▌")
        time.sleep(delay)
    output.markdown(typed)

# ──────────────────────────────────────────────────────────────
# Streamlit UI
st.set_page_config(page_title="Document Search", layout="wide")
st.title("📄 Word Document Search App")

st.markdown("#### 🏠 Enter Property Name")
user_input = st.text_input("property name without worrying about exact spelling", placeholder="e.g., Santosha Green City", key="property_input")

matched_docs = []
selected_docs = []
if user_input.strip():
    if user_input.strip().isdigit():
        matched_docs = search_documents(file_id=user_input.strip())
    else:
        matched_docs = fuzzy_match_properties(user_input.strip())

    if matched_docs:
        st.success(f"Found {len(matched_docs)} matching properties.")
        for doc in matched_docs:
            label = f"📁 File ID: {doc['file_id']} — 🏠 {doc['property_name']}"
            if st.checkbox(label, key=f"chk_{doc['file_id']}"):
                selected_docs.append(doc)
    else:
        st.warning("No matching properties found.")

st.markdown("#### 🧠 Ask a Question to AI about the above properties")
question = st.text_input("What do you want to know? (e.g., owner name, jantry value)", key="ai_question_input")
ask_button = st.button("Ask AI")

# Determine which docs to operate on
docs_to_use = selected_docs if selected_docs else matched_docs

if ask_button and question.strip() and docs_to_use:
    is_compare_mode = "compare" in question.lower()
    structured_keywords = {"owner", "jantry", "market value", "distress", "file id", "area", "rate", "comparison"}
    is_general_query = all(kw not in question.lower() for kw in structured_keywords)

    if is_compare_mode:
        keywords = extract_keywords_from_question(question)
        keywords = [kw for kw in keywords if kw != "compare"]
        attribute = " ".join(keywords).strip().title()

        if len(docs_to_use) > 5:
            st.warning("Comparing more than 5 documents may take longer. Please wait...")

        st.markdown(f"### 📊Comparison for: **{attribute}**")

        results = []
        for doc in docs_to_use:
            chunks = chunk_document(doc['content'])

            def score_chunk(chunk):
                return sum(1 for kw in keywords if kw in chunk.lower())

            top_chunk = sorted(chunks, key=score_chunk, reverse=True)[0]

            prompt = f'''
            You are extracting document data for property comparison.
            From the below document chunk, extract only the {attribute} if available.

            Document:
            \'\'\'{top_chunk}\'\'\'

            Provide answer in format:
            Answer: <value>
            '''

            response = query_ollama(prompt)
            match = re.search(r"Answer[:\-]\s*(.*)", response)
            final_answer = match.group(1).strip() if match else dynamic_regex_fallback(doc['content'], question)

            results.append({
                "File ID": doc["file_id"],
                "Property": doc["property_name"],
                attribute: final_answer
            })

        df = pd.DataFrame(results)
        st.markdown("<style> .css-1v0mbdj th, .css-1v0mbdj td { font-size: 18px !important; } </style>", unsafe_allow_html=True)
        st.dataframe(df, height=450)

    else:
        for doc in docs_to_use:
            st.markdown(f"### 📁 File ID: {doc['file_id']} — 🏠 {doc['property_name']}")
            chunks = chunk_document(doc['content'])
            keywords = extract_keywords_from_question(question)

            def score_chunk(chunk):
                chunk_lower = chunk.lower()
                return sum(1 for kw in keywords if kw in chunk_lower)

            sorted_chunks = sorted(chunks, key=score_chunk, reverse=True)
            top_chunk = sorted_chunks[0]

            if is_general_query:
                prompt = f"""
                You are a helpful assistant.
                Based on the below document, answer the user's question as best as possible.

                Document:
                '''{top_chunk}'''

                Question:
                "{question}"

                Answer:
                """
            else:
                prompt = f"""
                You are a helpful assistant for property document analysis.

                Document:
                '''{top_chunk}'''

                Question:
                "{question}"

                Answer (only if it is based on document text above):
                """

            response = query_ollama(prompt)
            if response:
                simulate_typing(f"**Answer:** {response.strip()}")
            else:
                st.error("⚠️ No response received from the model.")

            st.markdown("---")
