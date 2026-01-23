
# ------------------ Imports ------------------
from typing import TypedDict, Optional, Dict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from PyPDF2 import PdfReader
import os, json, re
from dotenv import load_dotenv

load_dotenv()


from db import init_db, check_duplicate, insert_invoice

# ------------------ Simple Normalizers ------------------
def normalize_invoice_number(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    return val.strip().upper()

def normalize_vendor(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    return val.strip().title()

def normalize_amount(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    clean = re.sub(r"[₹$€£,]", "", str(val))
    try:
        return str(float(clean))
    except ValueError:
        return None

# ------------------ LLM Setup ------------------
def get_llm():
    return ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"), # type: ignore
        temperature=0.1
    )

# ------------------ State ------------------
class InvoiceState(TypedDict, total=False):
    pdf_text: str
    invoice_number: Optional[str]
    vendor: Optional[str]
    date: Optional[str]
    amount: Optional[str]
    tax: Optional[str]
    po_number: Optional[str]
    validation_errors: Optional[Dict[str, str]]
    is_duplicate: Optional[bool]
    routing_decision: Optional[str]
    summary: Optional[str]

# ------------------ Helper: Read PDF ------------------
def read_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

# ------------------ Helper: Regex Extraction ------------------
def _extract_fields_with_regex(text: str) -> dict:
    """Extract invoice fields using centralized regex patterns."""
    
    patterns = {
        "invoice_number": [
            r"(?:Invoice\s*#|Invoice\s*No\.?|Invoice\s*Number)[:\-]?\s*([A-Z0-9\-\/]+)",
            r"\bINV[-/]?\d{3,}\b",
        ],
        "vendor": [
            r"(?:Vendor|Supplier|From)[:\-]\s*(.+)"
        ],
        "date": [
            r"Invoice\s*Date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"Invoice\s*Date\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
            r"Invoice\s*Date\s*[:\-]?\s*([0-9]{1,2}-[A-Za-z]{3}-[0-9]{4})",
        ],
        "amount": [
            r"(?:Total\s*Due|Amount\s*Due|Total)[:\-]?\s*([$₹€£]?\s?[\d,]+(?:\.\d{2})?)",
            r"([$₹€£]\s?[\d,]+)"
        ],
        "tax": [
            r"(?:Tax|GST|VAT)[:\-]?\s*([\d,.%]+)"
        ],
        "po_number": [
            r"(?:PO\s*#|PO\s*No\.?|Purchase\s*Order)[:\-]?\s*([A-Z0-9\-\/]+)"
        ]
    }

    results = {}

    for field, field_patterns in patterns.items():
        value = None
        # Vendor fallback: first line without numbers and not all uppercase
        if field == "vendor":
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for line in lines:
                if not re.search(r"\d", line) and not re.fullmatch(r"[A-Z\s]+", line):
                    value = line
                    break

        # Try regex patterns
        if not value:
            for p in field_patterns:
                m = re.search(p, text, re.IGNORECASE)
                if m:
                    value = m.group(1).strip()
                    break

        results[field] = value

    return results

@tool
def extract_fields_with_regex(text: str) -> dict:
    """Regex-based invoice field extractor (tool)."""
    return _extract_fields_with_regex(text)


# ------------------ Node 1: Extract Fields ------------------
def extract_node(state: InvoiceState) -> InvoiceState:
    llm = get_llm().bind_tools([extract_fields_with_regex])

    prompt = f"""
    You are an invoice extraction agent.

    Goal:
    - Extract invoice_number, vendor, date, amount, tax, po_number
    - If the text is messy or ambiguous, CALL the regex tool

    Rules:
    - Prefer semantic understanding
    - Use tools when structure is needed
    - Return JSON only

    Invoice text:
    {state.get("pdf_text", "")}  
    """

    response = llm.invoke(prompt)

    llm_data = {}

    # ------------------ Handle Tool Calls ------------------
    if response.tool_calls:
        for call in response.tool_calls:
            if call["name"] == "extract_fields_with_regex":
                llm_data = call["args"]
    else:
        try:
            llm_data = json.loads(response.content) # type: ignore
        except Exception:
            llm_data = {}

    # ------------------ Guaranteed Safety Fallback ------------------
    regex_data = _extract_fields_with_regex(state["pdf_text"]) # type: ignore

    combined = {
        k: llm_data.get(k) or regex_data.get(k)
        for k in regex_data
    }

    # ------------------ Normalize ------------------
    combined["invoice_number"] = normalize_invoice_number(combined.get("invoice_number"))
    combined["vendor"] = normalize_vendor(combined.get("vendor"))
    combined["amount"] = normalize_amount(combined.get("amount"))

    return {**state, **combined} # type: ignore


# ------------------ Node 2: Validation ------------------
def validate_node(state: InvoiceState) -> InvoiceState:
    errors = {}
    if not state.get("invoice_number"):
        errors["invoice_number"] = "Missing invoice number"
    if not state.get("vendor"):
        errors["vendor"] = "Vendor name missing."
    if not state.get("amount"):
        errors["amount"] = "Missing amount"
    return {**state, "validation_errors": errors}

# ------------------ Node 3: Duplicate Check ------------------
def duplicate_node(state: InvoiceState) -> InvoiceState:
    duplicate = check_duplicate(
        state.get("invoice_number"),
        state.get("vendor"),
        state.get("amount"),
    )
    return {**state, "is_duplicate": duplicate}

# ------------------ Node 4: Routing ------------------
def routing_node(state: InvoiceState) -> InvoiceState:
    # Remove currency and commas
    amount_val = 0.0
    if state.get("amount"):
        amount_val = float(re.sub(r"[₹$€£,]", "", str(state["amount"]))) # type: ignore
    decision = "Finance Approval" if amount_val > 10000 else "Auto Approval"
    return {**state, "routing_decision": decision}

# ------------------ Node 5: Summary ------------------
def summary_node(state: InvoiceState) -> InvoiceState:
    llm = get_llm()
    prompt = PromptTemplate.from_template("""
    Summarize this invoice in 2 short sentences
    for a finance user.

    Invoice text:
    {text}
    """)
    response = llm.invoke(prompt.format(text=state.get("pdf_text", ""))) # type: ignore
    return {**state, "summary": response.content.strip()} # type: ignore

# ------------------ Node 6: Persist ------------------
def persist_node(state: InvoiceState) -> InvoiceState:
    if not state.get("is_duplicate") and not state.get("validation_errors"):
        insert_invoice({
            "invoice_number": state.get("invoice_number"),
            "vendor": state.get("vendor"),
            "amount": state.get("amount"),
            "date": state.get("date"),
            "tax": state.get("tax"),
            "po_number": state.get("po_number"),
        })
    return state

# ------------------ Build Graph ------------------
def build_graph():
    graph = StateGraph(InvoiceState)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("duplicate", duplicate_node)
    graph.add_node("route", routing_node)
    graph.add_node("summary", summary_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", "duplicate")
    graph.add_edge("duplicate", "route")
    graph.add_edge("route", "summary")
    graph.add_edge("summary", "persist")
    graph.add_edge("persist", END)

    return graph.compile()