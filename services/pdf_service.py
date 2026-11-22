"""PDF validation and text extraction using PyMuPDF.
Files are processed in memory and are never written to disk or executed."""
import re

MAX_PAGES = 100        # pages read from a PDF
MIN_TEXT_CHARS = 200   # below this the PDF is treated as having no usable text


class PDFError(Exception):
    """Raised with a message that is safe to show to the student."""


def validate_upload(file_storage, max_mb):
    """Check the uploaded file and return its bytes. Raises PDFError if invalid."""
    if file_storage is None or not file_storage.filename:
        raise PDFError("Choose a PDF file to upload.")

    if not file_storage.filename.lower().endswith(".pdf"):
        raise PDFError("Only PDF files are allowed.")

    data = file_storage.read(max_mb * 1024 * 1024 + 1)  # read one byte past the limit to detect oversize
    if not data:
        raise PDFError("This file is empty.")
    if len(data) > max_mb * 1024 * 1024:
        raise PDFError(f"File is too large. The limit is {max_mb} MB.")
    if not data.lstrip()[:5] == b"%PDF-":  # real PDFs start with this signature, whatever the file name says
        raise PDFError("This file is not a valid PDF.")
    return data


def extract_text(pdf_bytes):
    """Return cleaned text from the PDF. Raises PDFError for unreadable or text-less files."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise PDFError("PyMuPDF is not installed. Run: pip install -r requirements.txt")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        raise PDFError("This PDF could not be opened. It may be corrupted.")

    try:
        if doc.needs_pass:
            raise PDFError("This PDF is password protected. Remove the password and try again.")
        parts = []
        for page_number, page in enumerate(doc):
            if page_number >= MAX_PAGES:
                break
            parts.append(page.get_text())
    except PDFError:
        raise
    except Exception:
        raise PDFError("This PDF could not be read. It may be corrupted.")
    finally:
        doc.close()

    text = re.sub(r"[ \t]+", " ", "\n".join(parts))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()

    if len(text) < MIN_TEXT_CHARS:
        raise PDFError(
            "No readable text was found in this PDF. It may be a scanned document or images only. "
            "Upload a PDF with selectable text."
        )
    return text
