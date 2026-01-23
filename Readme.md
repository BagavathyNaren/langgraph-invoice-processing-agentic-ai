the project root.

conda activate "h:\AGENTIC AI\DAY 2 - LANGGRAPH INVOICE PROCESSING ASSISTANT\.conda"

markdown
# 📄 Invoice Assistant (LangGraph + Streamlit)

An end‑to‑end **invoice processing assistant** built with **Streamlit**, **LangGraph**, **OpenAI**, and **SQLite**.

The app lets you:

- **Upload invoice PDFs**
- **Extract key fields** (invoice number, vendor, date, amount, tax, PO number)
- **Validate required data**
- **Detect duplicate invoices** using a composite hash in SQLite
- **Decide routing** (auto‑approval vs finance approval)
- **Summarize the invoice** for finance users
- **Generate and send a pre‑filled approval email** via SMTP

---

## 🧱 Project Structure

```text
langgraph/
  app.py               # Streamlit UI & email sending
  Invoice_agent.py     # LangGraph workflow & LLM logic
  db.py                # SQLite DB helpers (init, insert, duplicate check)
  invoices.db          # SQLite database (created automatically)
  sample_invoice*.pdf  # Sample invoices
  SL.png               # Logo image used in UI
  .env                 # Environment variables (not committed)
```*
⚙️ Core Components
Streamlit UI (
app.py
)
File upload for PDF invoices.
Shows validation errors, duplicate status, routing decision, extracted fields, and summary.
Lets user review and send an approval email.
LangGraph Workflow (
Invoice_agent.py
)
extract_node

Uses OpenAI + a regex tool to extract: invoice_number, vendor, date, amount, tax, po_number.
validate_node

Ensures mandatory fields exist and collects validation_errors.
duplicate_node

Checks for duplicates in SQLite using a composite hash of (invoice_number, vendor, amount).
routing_node

Routes invoices above a threshold (e.g. > 10,000) to Finance Approval, otherwise marks as Auto Approval.
summary_node

Asks the LLM to provide a short, finance‑friendly summary of the invoice.
persist_node

Inserts non‑duplicate, valid invoices into the invoices table.
Database Layer (
db.py
)
Initializes invoices table (if not present).
Provides helper functions:
init_db()
 – create table.
check_duplicate()
 – check for an existing (invoice_number, vendor, amount) combo.
insert_invoice()
 – insert a new invoice (with composite hash_key).
🔑 Prerequisites
Python 3.9+ (recommended)
An OpenAI deployment (for ChatOpenAI)
An SMTP server (for sending approval emails)
📦 Suggested Dependencies
Create a requirements.txt similar to:

text
streamlit
langgraph
langchain-core
langchain-openai
python-dotenv
PyPDF2

Adjust versions as needed based on your environment.

Install:

bash
pip install -r requirements.txt
🔐 Environment Variables
The project uses a 
.env
 file and os.getenv to configure LLM and email settings.

Create a 
.env
 file with:

env
# OpenAI
OPENAI_API_KEY=your_openai_key


# Database (optional override)
INVOICE_DB_PATH=invoices.db

# SMTP / Email
SMTP_SERVER=smtp.yourmailserver.com
SMTP_PORT=587
SMTP_USER=your_smtp_user
SMTP_PASS=your_smtp_password

MAIL_FROM_NAME=Finance Team
MAIL_FROM_ADDRESS=financeteam@demo.com
MAIL_TO_ADDRESS=ap@vendor-demo.com
Ensure 
.env
 is not committed to version control.

🚀 How to Run
Ensure dependencies are installed (see above).
Place 
.env
 file in the project root.
From the project directory, run:
bash
streamlit run app.py
Open the Streamlit URL shown in the terminal (typically
http://localhost:8501).
The DB is initialized automatically on app startup (via 
init_db()
).

🧪 Using the App
Upload an invoice PDF
Use the Invoice Processing tab.
Optionally add notes in the sidebar to be included in the email.
Process invoice
Click Process Invoice.
The workflow runs:
Extract → Validate → Duplicate Check → Route → Summary → Persist.
Review results
Processing Status: validation count, duplicate flag, routing decision.
Validation Errors: displayed if mandatory fields are missing.
Duplicate Warning: if a matching invoice already exists in 
invoices.db
.
Extracted Invoice Details: vendor, tax, date, PO number, invoice number, amount.
Invoice Summary: short narrative summary for finance.
Approval email
A draft email is generated using extracted fields and summary.
You can edit this email in the UI text area.
Send
Click Approve & Send Email.
The app uses your SMTP settings to send the email.
Success/failure status is shown in the UI.
🧠 LangGraph Workflow Overview
The second tab, Process Overview, documents the process for business/tech users:

Objective, benefits, and governance aspects.
A simple Graphviz flow diagram:
text
Extract → Validate → Duplicate → Route → Summary → Persist → Email
This makes it easy to explain the solution in demos or stakeholder sessions.

🗄️ Database Details
Table: invoices

id (INTEGER, PK)
invoice_number (TEXT)
vendor (TEXT)
amount (TEXT)
date (TEXT)
tax (TEXT)
po_number (TEXT)
hash_key (TEXT, UNIQUE)
Composite of:
invoice_number (uppercased & trimmed)
vendor (uppercased & trimmed)
amount (trimmed)
hash_key is used for duplicate detection.

🛡️ Notes & Limitations
PDF extraction uses PyPDF2 and expects text-based PDFs.
Scanned images may need OCR; currently the app shows an error if text extraction fails.
Azure OpenAI settings must be valid; otherwise extraction and summary will fail.
SMTP must be reachable and credentials valid to send emails.
🧩 Extensibility Ideas
Add OCR (e.g., OpenAI Computer Vision / Tesseract) for scanned PDFs.
Enrich routing logic with:
Cost centers
Approver hierarchy
Escalation rules
Add a historical invoice explorer UI on top of 
invoices.db
.
Integrate with an ERP / accounting system (SAP, Oracle, etc.).
📫 Support
If you run into issues:

Confirm 
.env
 variables are set correctly.
Check console logs for Python exceptions.
Verify that OpenAI and SMTP services are reachable from your network.
