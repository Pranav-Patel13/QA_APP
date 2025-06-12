import os
import re
import html
import hashlib
from datetime import datetime
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph
import mysql.connector
import win32com.client as win32
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# ---------- Configuration ----------
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'word_documents'
}

TEMP_DOWNLOAD_DIR = "./downloaded_docs"
# GOOGLE_FOLDER_ID = "1iWHSGoF70XgyEMwExpzqStX1WviSQgng"  # <-- Replace with your folder ID

import re

def extract_folder_id(url):
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else url

# Usage
folder_url = "https://drive.google.com/drive/folders/1iWHSGoF70XgyEMwExpzqStX1WviSQgng?usp=drive_link"
GOOGLE_FOLDER_ID = extract_folder_id(folder_url)


# ---------- Google Drive Setup ----------
def authenticate_google_drive():
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    return GoogleDrive(gauth)

def is_file_already_inserted(file_id, cursor):
    query = "SELECT COUNT(*) FROM updated_documents WHERE file_id = %s"
    cursor.execute(query, (file_id,))
    count = cursor.fetchone()[0]
    return count > 0

def list_all_doc_files(drive, folder_id):
    all_files = []

    def traverse_folder(folder_id):
        file_list = drive.ListFile({
            'q': f"'{folder_id}' in parents and trashed=false"
        }).GetList()

        for file in file_list:
            mime = file['mimeType']
            if mime == 'application/vnd.google-apps.folder':
                # Recurse into subfolder
                traverse_folder(file['id'])
            elif file['title'].lower().endswith(('.doc', '.docx')):
                all_files.append(file)

    traverse_folder(folder_id)
    return all_files


def download_file(drive_file, download_dir):
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    filepath = os.path.join(download_dir, drive_file['title'])

    if os.path.exists(filepath):
        print(f"⏭️ Skipped download (already exists): {filepath}")
        return filepath

    drive_file.GetContentFile(filepath)
    print(f"✅ Downloaded: {filepath}")
    return filepath


# ---------- Word Processing ----------
def convert_doc_to_docx(doc_path):
    try:
        if not doc_path.lower().endswith(".doc") or doc_path.lower().endswith(".docx"):
            return doc_path

        doc_path = os.path.normpath(os.path.abspath(doc_path))
        new_path = doc_path + "x"

        word = win32.gencache.EnsureDispatch('Word.Application')
        word.Visible = False
        word.DisplayAlerts = False

        doc = word.Documents.Open(doc_path)
        doc.SaveAs(new_path, FileFormat=16)  # 16 = wdFormatDocumentDefault (.docx)
        doc.Close(False)
        word.Quit()
        print(f"🔄 Converted: {doc_path} → {new_path}")
        return new_path

    except Exception as e:
        print(f"❌ Error converting {doc_path}: {e}")
        return None

def iter_block_items(parent):
    for child in parent.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def normalize_text(text):
    return ' '.join(text.strip().split())

def normalize_table_text(table):
    lines = []
    for row in table.rows:
        cells = [normalize_text(cell.text) for cell in row.cells]
        if any(cells):  # ignore empty rows
            lines.append(" | ".join(cells))
    return "\n".join(lines)

def extract_content_as_text(filepath):
    doc = Document(filepath)

    content_lines = []
    seen_table_hashes = set()
    seen_para_hashes = set()

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = normalize_text(block.text)
            if not text:
                continue
            line_hash = hashlib.md5(text.lower().encode()).hexdigest()
            if line_hash in seen_para_hashes:
                continue
            seen_para_hashes.add(line_hash)

            if block.style.name.startswith("Heading") or block.style.name in ["Title", "Subtitle"]:
                content_lines.append(f"=== {text.upper()} ===")
            else:
                content_lines.append(text)

        elif isinstance(block, Table):
            norm_table_text = normalize_table_text(block)
            table_hash = hashlib.md5(norm_table_text.encode()).hexdigest()
            if table_hash in seen_table_hashes:
                continue
            seen_table_hashes.add(table_hash)

            content_lines.append("--- TABLE ---")
            content_lines.extend(norm_table_text.split("\n"))
            content_lines.append("--- END TABLE ---")

    return "\n".join(content_lines).strip()

# ---------- DB Insert ----------
def insert_into_db(file_id, property_name, content, conn, cursor):
    try:
        uploaded_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = """
            INSERT INTO updated_documents (file_id, property_name, content, uploaded_at)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (file_id, property_name, content, uploaded_at))
        conn.commit()
        print(f"📥 Inserted: {file_id} - {property_name}")
    except mysql.connector.Error as err:
        print(f"❌ DB Insert Error: {err}")
        conn.rollback()

# ---------- Main ----------
def process_documents_from_drive(folder_id, download_dir):
    drive = authenticate_google_drive()
    files = list_all_doc_files(drive, folder_id)

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    for file in files:
        file_path = download_file(file, download_dir)

        if file_path.lower().endswith('.doc') and not file_path.lower().endswith('.docx'):
            file_path = convert_doc_to_docx(file_path)
            if not file_path:
                continue

        if file_path.lower().endswith('.docx'):
            filename = os.path.splitext(os.path.basename(file_path))[0]
            parts = filename.split("_", 1)
            file_id = parts[0]
            property_name = parts[1].replace(",", " ") if len(parts) > 1 else "Unknown Property"

            # ⛔ Skip if already inserted
            if is_file_already_inserted(file_id, cursor):
                print(f"⏭️ Skipping already inserted file: {file_id}")
                continue

            content = extract_content_as_text(file_path)
            if content:
                insert_into_db(file_id, property_name, content, conn, cursor)
                try:
                    os.remove(file_path)
                    print(f"🗑️ Deleted file after insertion: {file_path}")
                except Exception as e:
                    print(f"⚠️ Could not delete file: {file_path}, reason: {e}")

    cursor.close()
    conn.close()

# ---------- Entry Point ----------
if __name__ == "__main__":
    if not GOOGLE_FOLDER_ID or GOOGLE_FOLDER_ID == "YOUR_FOLDER_ID_HERE":
        print("⚠️ Please set a valid GOOGLE_FOLDER_ID.")
    else:
        process_documents_from_drive(GOOGLE_FOLDER_ID, TEMP_DOWNLOAD_DIR)
    # convert_doc_to_docx("D:/internship/updated_fast_word_qa_app/downloaded_docs/10784_4_Pragati Green, Bill Verification_BOI_GIDC_Vapi.doc")
