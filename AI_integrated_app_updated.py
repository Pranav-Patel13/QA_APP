#
# import streamlit as st
# import html
# import re
# from bs4 import BeautifulSoup
# from search_util import chunk_document, fuzzy_match_properties
# from llm_util import query_ollama
#
# def clean_and_highlight(text, keyword):
#     import re
#     import html
#     from bs4 import BeautifulSoup
#
#     if not text:
#         return ""
#
#     soup = BeautifulSoup(text, "html.parser")
#     raw_text = soup.get_text(separator="\n")
#     lines = raw_text.splitlines()
#
#     formatted_lines = []
#     inside_table = False
#     text_buffer = ""
#
#     def highlight(text, keyword):
#         if not keyword:
#             return html.escape(text)
#         pattern = re.compile(re.escape(keyword), re.IGNORECASE)
#         return pattern.sub(
#             lambda m: f"<mark style='background-color: yellow; color: black'>{m.group(0)}</mark>",
#             html.escape(text)
#         )
#
#     def flush_buffer():
#         nonlocal text_buffer
#         if text_buffer:
#             formatted_lines.append(f"<p>{highlight(text_buffer.strip(), keyword)}</p>")
#             text_buffer = ""
#
#     for line in lines:
#         stripped = line.strip()
#         if not stripped:
#             flush_buffer()
#             formatted_lines.append("<br>")
#             continue
#
#         if stripped.startswith("===") and stripped.endswith("==="):
#             flush_buffer()
#             title = stripped.strip("=").strip()
#             formatted_lines.append(f"<h4 style='color:#4A90E2'>{html.escape(title)}</h4>")
#             continue
#
#         if stripped == "--- TABLE ---":
#             flush_buffer()
#             inside_table = True
#             formatted_lines.append("<table style='border-collapse:collapse; width:100%; margin-top:10px'>")
#             continue
#
#         if stripped == "--- END TABLE ---":
#             inside_table = False
#             formatted_lines.append("</table><br>")
#             continue
#
#         if inside_table:
#             flush_buffer()
#             cells = [
#                 f"<td style='border:1px solid #ccc; padding:6px'>{highlight(c.strip(), keyword)}</td>"
#                 for c in line.split("|")
#             ]
#             formatted_lines.append(f"<tr>{''.join(cells)}</tr>")
#         else:
#             if text_buffer and not text_buffer.endswith((".", ":", "?", "!", ")", "’", "”", "\"")):
#                 text_buffer += " " + stripped
#             else:
#                 flush_buffer()
#                 text_buffer = stripped
#
#     flush_buffer()
#     return "\n".join(formatted_lines)
#
# def extract_keywords_from_question(question, stopwords=None):
#     if stopwords is None:
#         stopwords = {
#             "what", "is", "the", "of", "a", "an", "in", "for", "and", "how", "many",
#             "list", "give", "tell", "me", "to", "find", "show", "details", "number"
#         }
#     tokens = re.findall(r'\b\w+\b', question.lower())
#     return [token for token in tokens if token not in stopwords and len(token) > 2]
#
# def dynamic_regex_fallback(doc_text: str, user_question: str) -> str:
#     keywords = extract_keywords_from_question(user_question)
#     if not keywords:
#         return "Not mentioned."
#
#     lines = doc_text.splitlines()
#     for line in lines:
#         line_lower = line.lower()
#         if all(k in line_lower for k in keywords):
#             match = re.search(r"[:|]\s*(\d{1,3}\s*\w+)", line)
#             if match:
#                 return match.group(1).strip()
#
#     keyword_pattern = r".*?".join(map(re.escape, keywords))
#     value_pattern = rf"{keyword_pattern}.*?[:|\-]?\s*([\w\s.,/-]+)"
#     match = re.search(value_pattern, doc_text, re.IGNORECASE)
#     if match:
#         return match.group(1).strip()
#
#     return "Not mentioned."
#
# st.set_page_config(page_title="Document Search", layout="wide")
# st.title("📄 Word Document Search App")
#
# user_input = st.text_input("🏠 Enter Property Name")
# matched_docs = []
#
# if user_input.strip():
#     matched_docs = fuzzy_match_properties(user_input.strip())
#     if matched_docs:
#         st.success(f"Found {len(matched_docs)} matching properties.")
#         for doc in matched_docs:
#             st.markdown(f"📁 File ID: `{doc['file_id']}` — 🏠 Property: **{doc['property_name']}**")
#     else:
#         st.warning("No matching properties found.")
#
# question = st.text_input("🧠 Ask a Question to AI about the above properties")
#
# if question.strip() and matched_docs:
#     for doc in matched_docs:
#         st.markdown(f"### 📁 File ID: {doc['file_id']} — 🏠 {doc['property_name']}")
#         chunks = chunk_document(doc['content'])
#         keywords = extract_keywords_from_question(question)
#
#         def score_chunk(chunk):
#             chunk_lower = chunk.lower()
#             return sum(1 for kw in keywords if kw in chunk_lower)
#
#         sorted_chunks = sorted(chunks, key=score_chunk, reverse=True)
#         final_answer = "Not mentioned."
#
#         for chunk in sorted_chunks:
#             prompt = f"""
# You are a helpful assistant for property document analysis.
#
# Document:
# \"\"\"{chunk}\"\"\"
#
# Question:
# \"{question}\"
#
# Answer (only if it is based on document text above):
# """
#             response = query_ollama(prompt)
#             if "not found" not in response.lower() and len(response.strip()) > 3:
#                 final_answer = response.strip()
#                 break
#         else:
#             final_answer = dynamic_regex_fallback(doc['content'], question)
#
#         st.markdown(f"**Answer:** {final_answer}")
#         st.markdown("---")

import streamlit as st
import html
import re
from bs4 import BeautifulSoup
from search_util import chunk_document, fuzzy_match_properties
from llm_util import query_ollama

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

# ──────────────────────────────────────────────────────────────
# Streamlit UI
st.set_page_config(page_title="Document Search", layout="wide")
st.title("📄 Word Document Search App")

st.markdown("#### 🏠 Enter Property Name")
user_input = st.text_input("property name without worrying about exact spelling", placeholder="e.g., Santosha Green City", key="property_input")

matched_docs = []
if user_input.strip():
    matched_docs = fuzzy_match_properties(user_input.strip())
    if matched_docs:
        st.success(f"Found {len(matched_docs)} matching properties.")
        for doc in matched_docs:
            st.markdown(f"📁 File ID: `{doc['file_id']}` — 🏠 Property: **{doc['property_name']}**")
    else:
        st.warning("No matching properties found.")

st.markdown("#### 🧠 Ask a Question to AI about the above properties")
question = st.text_input("What do you want to know? (e.g., owner name, jantry value)", key="ai_question_input")

if st.button("Ask AI") and question.strip() and matched_docs:
    for doc in matched_docs:
        st.markdown(f"### 📁 File ID: {doc['file_id']} — 🏠 {doc['property_name']}")
        chunks = chunk_document(doc['content'])
        keywords = extract_keywords_from_question(question)

        def score_chunk(chunk):
            chunk_lower = chunk.lower()
            return sum(1 for kw in keywords if kw in chunk_lower)

        sorted_chunks = sorted(chunks, key=score_chunk, reverse=True)
        final_answer = "Not mentioned."

        for chunk in sorted_chunks:
            prompt = f"""
            You are a helpful assistant for property document analysis.
            
            Document:
            \"\"\"{chunk}\"\"\"
            
            Question:
            \"{question}\"
            
            Answer (only if it is based on document text above):
            """
            response = query_ollama(prompt)
            if "not found" not in response.lower() and len(response.strip()) > 3:
                final_answer = response.strip()
                break
        else:
            final_answer = dynamic_regex_fallback(doc['content'], question)

        st.markdown(f"**Answer:** {final_answer}")
        st.markdown("---")
