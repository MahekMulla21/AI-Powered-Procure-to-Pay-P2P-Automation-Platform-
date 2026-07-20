import psycopg2

import os
import psycopg2

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
 
# def save_file_record(file_name, file_path, file_type, file_size, status, reason):
#     conn = get_connection()
#     cur = conn.cursor()
 
#     query = """
#         INSERT INTO files_dataset
#         (file_name, file_path, file_type, file_size, status, reason)
#         VALUES (%s, %s, %s, %s, %s, %s)
#         RETURNING id;
#     """
 
#     cur.execute(query, (
#         file_name,
#         file_path,
#         file_type,
#         file_size,
#         status,
#         reason
#     ))
 
#     file_id = cur.fetchone()[0]
 
#     conn.commit()
#     cur.close()
#     conn.close()
 
#     return file_id
 
 
def save_file_record(file_name, file_path, file_type, file_size, status, reason, doc_type):  # ← add doc_type
    conn = get_connection()
    cur = conn.cursor()
 
    query = """
        INSERT INTO files_dataset
        (file_name, file_path, file_type, file_size, status, reason, doc_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
 
    cur.execute(query, (
        file_name,
        file_path,
        file_type,   # ← "pdf" / "docx"
        file_size,
        status,
        reason,
        doc_type     # ← "msa" / "sow" / "po" / "pr" / "invoice"
    ))
 
    file_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
 
    return file_id
 
def save_validation_logs(file_id, logs):
    conn = get_connection()
    cur = conn.cursor()
 
    query = """
        INSERT INTO validation_logs
        (file_id, rule_id, rule_name, result, message)
        VALUES (%s, %s, %s, %s, %s)
    """
 
    for log in logs:
        rule_id, rule_name, result, message = log
 
        cur.execute(query, (
            file_id,
            rule_id,
            rule_name,
            result,
            message
        ))
 
    conn.commit()
    cur.close()
    conn.close()