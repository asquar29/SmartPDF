PDF Outline Extractor
This Python project extracts structured document outlines (like headings, titles, and hierarchy) from PDF files using a combination of PDF parsing, OCR (Tesseract), and font-size-based heuristics. The extracted output is saved in a structured JSON format.

📂 Project Structure
graphql
Copy
Edit
.
├── main.py               # Main script for PDF processing
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker container definition
├── input/                # Folder for input PDF files
└── output/               # Folder where JSON results will be saved
🔧 What This Tool Does
Scans PDF files in input/

Detects the document title

Extracts section headings (H1, H2, H3) using:

Font size

Numbering patterns (e.g., 1., 1.1., 1.1.1)

Skips table content

Falls back to OCR using Tesseract if no text is found

Outputs a structured JSON in output/

✅ Step-by-Step Code Explanation
extract_outline(pdf_path)
Convert PDF to Images (OCR fallback):


images = convert_from_path(pdf_path, poppler_path=...)
Process Each Page with pdfplumber:

Extract characters (char) from the page.

Ignore characters inside tables.

Group characters into lines using Y-coordinates (top), normalized by line_tolerance.

Fallback to OCR if PDF has no extractable text:


ocr_text = pytesseract.image_to_string(images[page_number - 1])
Detect TOC pages using regex pattern.


def is_toc_page(lines): ...
Extract title using the largest font size on pages 1–2.

Map font sizes to heading levels (H1, H2, H3):


font_to_heading = {
    unique_sizes[1]: "H1",
    unique_sizes[2]: "H2",
    ...
}
Use regex to detect numeric outline levels (e.g., 1., 1.1.):


def detect_numbering_level(text): ...
Clean and skip noisy or irrelevant lines:


def should_skip(text, is_toc): ...
Construct final outline list with heading level, text, and page.

🐳 Running with Docker
 1. Build Docker Image

docker build --platform=linux/amd64 -t mysolutionname:somerandomidentifier .
🚀 2. Run the Extractor

docker run --rm \
  -v "$(pwd)/input:/app/input" \
  -v "$(pwd)/output:/app/output" \
  --network none \
  mysolutionname:somerandomidentifier
This will scan all PDFs inside input/ and generate .json files in output/.

📦 requirements.txt
Make sure this file includes:

nginx
Copy
Edit
pytesseract
pdfplumber
pdf2image
🛠 Dependencies (handled by Docker)
Python 3.10

Tesseract OCR

Poppler-utils (for pdf2image)

Ghostscript (optional, sometimes needed for some PDFs)

Output Example (output/sample.json)
json
Copy
Edit
{
  "title": "Sample Document Title",
  "outline": [
    { "level": "H1", "text": "1 Introduction", "page": 2 },
    { "level": "H2", "text": "1.1 Background", "page": 3 },
    { "level": "H3", "text": "1.1.1 Details", "page": 4 }
  ]
}
📝 Notes
The font-size to heading-level mapping may vary per document.

The script intelligently skips TOC pages when extracting real headings.

OCR fallback is used only when no text is extractable.