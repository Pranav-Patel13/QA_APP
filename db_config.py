# db_config = {
#     'host': 'localhost',
#     'user': 'root',
#     'password': '',  # Your MySQL password
#     'database': 'document_qadb'
# }
# db_config = {
#     'host': 'localhost',
#     'user': 'root',
#     'password': '',  # Your MySQL password
#     'database': 'word_documents'
# }

# db_config.py

import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="word_documents"
    )
