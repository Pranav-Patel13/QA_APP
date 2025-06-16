import streamlit as st
import html
import re
import time
from bs4 import BeautifulSoup
from search_util import chunk_document, fuzzy_match_properties, keyword_sql_match, search_documents
from llm_util import query_ollama
import pandas as pd

import json
import os

def load_synonym_dict(path="synonyms.json"):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    else:
        return {}

synonym_dict = load_synonym_dict()


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


def extract_keywords_from_question(question, stopwords=None):
    if stopwords is None:
        stopwords = {
            "what", "is", "the", "of", "a", "an", "in", "for", "and", "how", "many",
            "list", "give", "tell", "me", "to", "find", "show", "details", "number"
        }
    tokens = re.findall(r'\b\w+\b', question.lower())
    return [token for token in tokens if token not in stopwords and len(token) > 2]

def extract_comparison_attributes(question, synonym_dict):
    clean = question.lower().replace("compare", "")
    parts = re.split(r"\s+and\s+|,", clean)

    attributes = []
    for part in parts:
        key = part.strip()
        if not key:
            continue

        canonical = synonym_dict.get(key, key)

        # Try partial match if full not found
        for syn, canon in synonym_dict.items():
            if syn in key:
                canonical = canon
                break

        if canonical not in attributes:
            attributes.append(canonical)

    return attributes

def apply_synonym_mapping_to_question(question, synonym_dict):
    question_lower = question.lower()
    for syn, canon in synonym_dict.items():
        if syn in question_lower:
            question_lower = question_lower.replace(syn, canon)
    return question_lower


def dynamic_regex_fallback(doc_text: str, user_question: str) -> str:
    keywords = extract_keywords_from_question(user_question)
    if not keywords:
        return "Not mentioned."

    lines = doc_text.splitlines()
    # Try exact line match first
    for line in lines:
        line_lower = line.lower()
        if all(k in line_lower for k in keywords):
            # capture numeric or ₹-based value
            match = re.search(r"[:|]\s*([₹\d.,/-]+\s*\w*)", line)
            if match:
                return match.group(1).strip()

    # Try flexible pattern
    keyword_pattern = r".*?".join(map(re.escape, keywords))
    value_pattern = rf"{keyword_pattern}.*?[:|\-]?\s*([₹\d\s.,/-]+[a-zA-Z]*)"
    match = re.search(value_pattern, doc_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return "Not mentioned."

def attribute_specific_extract(attr: str, text: str) -> str:
    attr = attr.lower().strip()
    lines = text.splitlines()

    # Normalize attribute
    normalized_attr = re.sub(r"[^a-zA-Z0-9]", "", attr)

    for line in lines:
        line_clean = line.strip().lower()

        # Remove punctuation and spaces for flexible comparison
        line_key = re.sub(r"[^a-zA-Z0-9]", "", line_clean)

        if normalized_attr in line_key:
            # Try to extract value after : or -
            match = re.search(r"[:\-]\s*([₹Rs\.\d,]+[a-zA-Z\s/%.]*)", line)
            if match:
                value = match.group(1).strip()
                # Truncate overly long or verbose matches
                if 2 < len(value) < 80:
                    return value

    # Fallback: search full doc for "attr: value" type match
    loose_match = re.search(
        rf"{re.escape(attr)}[:\-]?\s*([₹Rs\.\d,]+[a-zA-Z\s/%.]*)",
        text,
        re.IGNORECASE
    )
    if loose_match:
        return loose_match.group(1).strip()

    return None


def simulate_typing(text, delay=0.04):
    output = st.empty()
    typed = ""
    for char in text:
        typed += char
        output.markdown(typed + "▌")
        time.sleep(delay)
    output.markdown(typed)

st.set_page_config(page_title="Document Search", layout="wide")
st.title("📄 Word Document Search App")

st.markdown("#### 🏠 Enter Property Name, File ID, or Owner Name")
user_input = st.text_input(
    "property name without worrying about exact spelling",
    placeholder="e.g., Santosha Green City or 12123 or Sejal Laxmanbhai",
    key="property_input"
)

matched_docs = []
selected_docs = []

if user_input.strip():
    user_input_clean = user_input.strip()

    if user_input_clean.isdigit():
        # Try file ID first
        matched_docs = search_documents(file_id=user_input_clean)

    if not matched_docs:
        # Try fuzzy property name
        matched_docs = fuzzy_match_properties(user_input_clean)

    if not matched_docs:
        # Try owner name match
        matched_docs = search_documents(owner_name=user_input_clean)
    if matched_docs:
        for doc in matched_docs:
            file_id = doc['file_id']
            label = f"📁 File ID: {file_id} — 🏠 {doc['property_name']}"
            if "owner_name" in doc and doc["owner_name"]:
                label += f" — 👤 {doc['owner_name']}"

            col1, col2 = st.columns([6, 1])
            with col1:
                checked = st.checkbox(label, key=f"chk_{file_id}")
                if checked:
                    selected_docs.append(doc)

            with col2:
                show_img = st.toggle("🖼️ Show Images", key=f"img_toggle_{file_id}")

            if show_img:
                col_a, col_b = st.columns(2)
                if doc.get("first_page_image"):
                    with col_a:
                        st.image(doc["first_page_image"], caption="🖼️ First Image", width=250)
                else:
                    with col_a:
                        st.warning("🚫 No first image")

                if doc.get("second_page_image"):
                    with col_b:
                        st.image(doc["second_page_image"], caption="🖼️ Second Image", width=250)
                else:
                    with col_b:
                        st.warning("🚫 No second image")
    else:
        st.warning("⚠️ No matching properties found.")

st.markdown("#### 🧠 Ask a Question to AI about the above properties")
question = st.text_input("What do you want to know? (e.g., owner name, jantry value)", key="ai_question_input")
ask_button = st.button("Ask AI")

# If user types and hits Enter (Streamlit reruns on Enter), this becomes True
if not ask_button and question:
    ask_button = True

# Determine which docs to operate on
docs_to_use = selected_docs if selected_docs else matched_docs

if ask_button and question.strip() and docs_to_use:
    is_compare_mode = "compare" in question.lower()
    structured_keywords = {"owner", "jantry", "market value", "distress", "file id", "area", "rate", "comparison"}
    is_general_query = all(kw not in question.lower() for kw in structured_keywords)

    if is_compare_mode:
        attributes = extract_comparison_attributes(question, synonym_dict)

        if len(docs_to_use) > 5:
            st.warning("Comparing more than 5 documents may take longer. Please wait...")

        results_dict = {}

        for attr in attributes:
            # ✅ extract keywords just like original working logic
            keywords = extract_keywords_from_question(attr)
            attribute = " ".join(keywords).strip().title()

            st.markdown(f"### 🔍 Extracting: **{attribute}**")

            for doc in docs_to_use:
                file_id = doc["file_id"]
                property_name = doc["property_name"]

                if file_id not in results_dict:
                    results_dict[file_id] = {
                        "File ID": file_id,
                        "Property": property_name
                    }

                chunks = chunk_document(doc['content'])

                def score_chunk(chunk):
                    return sum(1 for kw in keywords if kw in chunk.lower())

                top_chunk = sorted(chunks, key=score_chunk, reverse=True)[0]

                prompt = f'''
                You are extracting document data for property comparison.
                From the below document chunk, extract only the {attribute} if available.

                Document:
                \'\'\'
                {top_chunk}
                \'\'\'

                Provide answer in format:
                Answer: <value>
                '''
                response = query_ollama(prompt)
                match = re.search(r"Answer[:\-]\s*(.*)", response)
                final_answer = match.group(1).strip() if match else dynamic_regex_fallback(doc['content'], attr)

                results_dict[file_id][attribute] = final_answer

        # ✅ Final table with all attributes
        df = pd.DataFrame(results_dict.values())
        st.markdown("<style> .css-1v0mbdj th, .css-1v0mbdj td { font-size: 18px !important; } </style>",
                    unsafe_allow_html=True)
        st.dataframe(df, height=500)

    else:
        # 🧠 Apply synonym mapping to the whole question
        mapped_question = apply_synonym_mapping_to_question(question, synonym_dict)
        st.caption(f"🧠 Mapped Question: `{mapped_question}`")  # Optional for debugging

        for doc in docs_to_use:
            st.markdown(f"### 📁 File ID: {doc['file_id']} — 🏠 {doc['property_name']}")
            chunks = chunk_document(doc['content'])

            # Extract keywords from the mapped version
            keywords = extract_keywords_from_question(mapped_question)


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
                "{mapped_question}"

                Answer:
                """
            else:
                prompt = f"""
                You are a helpful assistant for property document analysis.

                Document:
                '''{top_chunk}'''

                Question:
                "{mapped_question}"

                Answer (only if it is based on document text above):
                """

            response = query_ollama(prompt)
            simulate_typing(f"**Answer:** {response.strip()}")
            st.markdown("---")
