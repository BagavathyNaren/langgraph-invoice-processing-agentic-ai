# file: app.py
import os
import tempfile
import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from Invoice_agent import build_graph, read_pdf, init_db

# ----------------- Init DB -----------------
init_db()

# ----------------- Config (from ENV only) -----------------
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Finance Team")
MAIL_FROM_ADDRESS = os.getenv("MAIL_FROM_ADDRESS", "financeteam@demo.com")
MAIL_TO_ADDRESS = os.getenv("MAIL_TO_ADDRESS", "ap@vendor-demo.com")

# ----------------- Page Config -----------------
col_logo, col_title = st.columns([2, 10])

with col_logo:
    st.image("SL.png", width=300)


st.set_page_config(
    page_title="Invoice Assistant",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Invoice Assistant")
st.caption(
    "Upload an invoice PDF to extract fields, validate, detect duplicates, "
    "route for approval, summarize, and generate a finance-ready email."
)

# ----------------- Sidebar -----------------
st.sidebar.header("Optional Notes")
user_notes = st.sidebar.text_area(
    "Notes to include in approval email",
    height=100
)

# ----------------- Tabs -----------------
tab1, tab2 = st.tabs(["Invoice Processing", "Process Overview"])

# =============================================================================
# TAB 1 — INVOICE PROCESSING
# =============================================================================
with tab1:
    uploaded = st.file_uploader("Upload Invoice PDF", type=["pdf"])
    run_btn = st.button(
        "Process Invoice",
        type="primary",
        disabled=(uploaded is None)
    )

    if run_btn and uploaded:
        with st.spinner("Reading invoice PDF..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name

            pdf_text = read_pdf(tmp_path)
            os.unlink(tmp_path)

        if not pdf_text.strip():
            st.error("❌ Unable to extract text. OCR required for scanned PDFs.")
        else:
            with st.spinner("Running invoice intelligence workflow..."):
                graph = build_graph()
                from Invoice_agent import InvoiceState
                result = graph.invoke({
                    "pdf_text": pdf_text,
                    "user_notes": user_notes or None
                }) # type: ignore
                duplicate_text = ("YES ⚠️ (Duplicate invoice detected – please review carefully)"
                                  if result.get("is_duplicate") else "NO")
                st.session_state["invoice_result"] = result

                # ----------------- Email Template -----------------
                email_body = f"""Dear Accounts Payable Team,

Please review and process the following invoice:

Invoice Number : {result.get("invoice_number") or "N/A"}
Vendor         : {result.get("vendor") or "N/A"}
Invoice Date   : {result.get("date") or "N/A"}
Invoice Amount : ₹{result.get("amount") or "N/A"}
Duplicate Invoice: {duplicate_text}

Summary:
{result.get("summary") or "—"}


This invoice has been validated and routed by the Invoice Assistant.

Regards,
{MAIL_FROM_NAME}
"""

                st.session_state["email_text"] = email_body

    # ----------------- Results -----------------
    if "invoice_result" in st.session_state:
        result = st.session_state["invoice_result"]

        st.subheader("📊 Processing Status")
        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Validation Errors",
            len(result.get("validation_errors") or {})
        )
        col2.metric(
            "Duplicate Invoice",
            "Yes" if result.get("is_duplicate") else "No"
        )
        col3.metric(
            "Routing Decision",
            result.get("routing_decision") or "—"
        )

        if result.get("validation_errors"):
            st.error("⚠ Validation issues detected")
            for k, v in result["validation_errors"].items():
                st.write(f"- **{k}**: {v}")
        else:
            st.success("✅ Invoice passed validation checks")

        if result.get("is_duplicate"):
            st.warning("⚠ Duplicate invoice detected")

        # ----------------- Extracted Fields -----------------
        st.subheader("🧾 Extracted Invoice Details")
        a, b, c = st.columns(3)

        a.info(f"**Vendor**\n{result.get('vendor') or '—'}\n\n**Tax**\n{result.get('tax') or '—'}")
        b.info(f"**Invoice Date**\n{result.get('date') or '—'}\n\n**PO Number**\n{result.get('po_number') or '—'}")
        c.info(f"**Invoice Number**\n{result.get('invoice_number') or '—'}\n\n**Amount**\n₹{result.get('amount') or '—'}")

        # ----------------- Summary -----------------
        st.subheader("📄 Invoice Summary")
        st.markdown(result.get("summary") or "No summary generated.")

        # ----------------- Email Draft -----------------
        st.subheader("✉️ Approval Email (Pre-configured)")
        email_text = st.text_area(
            "Review email before approval",
            st.session_state.get("email_text", ""),
            height=220
        )
        st.session_state["email_text"] = email_text

        st.divider()

        # ----------------- Approval Action -----------------
        st.subheader("✅ Approve & Send")

        # st.write(f"**From:** {MAIL_FROM_NAME} <{MAIL_FROM_ADDRESS}>")
        # st.write(f"**To:** {MAIL_TO_ADDRESS}")

        if st.button("Approve & Send Email", type="primary"):
            try:
                msg = MIMEMultipart()
                msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM_ADDRESS}>"
                msg["To"] = MAIL_TO_ADDRESS
                msg["Subject"] = f"Invoice Approval – {result.get('invoice_number') or 'N/A'}"
                msg.attach(MIMEText(email_text, "plain")) # type: ignore

                server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT) # type: ignore
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS) # type: ignore
                server.send_message(msg)
                server.quit()

                st.success("🎉 Invoice approved and email sent successfully")

            except Exception as e:
                st.error(f"❌ Email sending failed: {e}")

# =============================================================================
# TAB 2 — PROCESS OVERVIEW
# =============================================================================
with tab2:
    st.header("🔹 Invoice Assistant – Process Overview")

    st.subheader("Objective")
    st.write("""
    The Invoice Assistant automates the end-to-end invoice lifecycle:
    extraction, validation, deduplication, routing, summarization,
    and finance approval communication.
    """)

    st.subheader("LangGraph Workflow")
    st.write("""
    Extract → Validate → Duplicate Check → Routing → Summary → Persist → Approval Email
    """)

    st.subheader("Workflow Visualization")
    st.graphviz_chart("""
    digraph InvoiceFlow {
        rankdir=LR;
        node [shape=rect, style="rounded,filled", fillcolor="#E3F2FD"];

        Extract -> Validate -> Duplicate -> Route -> Summary -> Persist -> Email;
    }
    """)

    st.subheader("Why This Matters")
    st.write("""
    - Reduces manual invoice processing time
    - Prevents duplicate payments
    - Ensures governance & approval controls
    - Provides audit-ready traceability
    - Designed for business & technical stakeholders
    """)