import mysql.connector
import streamlit as st

def get_connection():
    return mysql.connector.connect(
        host=st.secrets["localhost"],
        user=st.secrets["root"],
        password=st.secrets[""],
        database=st.secrets["word_documents"]
    )
