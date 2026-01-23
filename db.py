# file: db.py
import sqlite3
from typing import Optional, Dict, Any
import os

DB_PATH = os.getenv("INVOICE_DB_PATH", "invoices.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT,
    vendor TEXT,
    amount TEXT,
    date TEXT,
    tax TEXT,
    po_number TEXT,
    hash_key TEXT UNIQUE,  -- composite signature for duplicates
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_conn()
    with conn:
        conn.executescript(SCHEMA)
    conn.close()

def composite_hash(invoice_number: Optional[str], vendor: Optional[str], amount: Optional[str]) -> Optional[str]:
    if not invoice_number or not vendor or not amount:
        return None
    # Normalize to reduce false negatives
    key = f"{(invoice_number or '').strip().upper()}|{(vendor or '').strip().upper()}|{(amount or '').strip()}"
    return key

def check_duplicate(invoice_number: Optional[str], vendor: Optional[str], amount: Optional[str]) -> bool:
    hash_key = composite_hash(invoice_number, vendor, amount)
    if not hash_key:
        return False
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM invoices WHERE hash_key = ?", (hash_key,))
        return cur.fetchone() is not None
    finally:
        conn.close()

def insert_invoice(record: Dict[str, Any]) -> None:
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """INSERT OR IGNORE INTO invoices
                (invoice_number, vendor, amount, date, tax, po_number, hash_key)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.get("invoice_number"),
                    record.get("vendor"),
                    record.get("amount"),
                    record.get("date"),
                    record.get("tax"),
                    record.get("po_number"),
                    composite_hash(record.get("invoice_number"), record.get("vendor"), record.get("amount")),
                ),
            )
    finally:
        conn.close()
