import os
import re
import json
import pytesseract
import pdfplumber
from collections import defaultdict
from pdf2image import convert_from_path
import argparse

# ---------------- Configuration Defaults ----------------
DEFAULT_LINE_TOLERANCE = 2
DEFAULT_OCR_FONT_SIZE = 10

# Optional: Set tesseract path if needed
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---------------- Helper Functions ----------------
def is_heading_candidate(text):
    return len(text.split()) <= 15

def detect_numbering_level(text):
    match = re.match(r'^\d+(\.\d+)*', text.strip())
    if not match:
        return None
    depth = text.count(".") + 1
    if depth == 1:
        return "H1"
    elif depth == 2:
        return "H2"
    elif depth >= 3:
        return "H3"
    return None

def should_skip(text, is_toc=False):
    text = text.strip()
    if len(text) < 3:
        return True
    if is_toc:
        return True
    if re.match(r'^0\.\d+', text):  # revision numbers
        return True
    if re.match(r'^\d{4}\.?$', text):  # year only
        return True
    if len(text.split()) > 15:  # too long
        return True
    return False

def clean_text(text):
    text = re.sub(r'\.{2,}', '', text)
    text = re.sub(r'\s+\d+$', '', text)
    return text.strip()

def is_toc_page(lines):
    toc_pattern = re.compile(r'^(\d+(\.\d+)*)\s+.+\s+\d+$')
    count = sum(1 for line in lines if toc_pattern.match(line))
    return count >= 3

def inside_table(x0, y0, x1, y1, tables):
    for table in tables:
        tx0, ty0, tx1, ty1 = table
        if x0 >= tx0 and x1 <= tx1 and y0 >= ty0 and y1 <= ty1:
            return True
    return False

# ---------------- Main Extraction Function ----------------
def extract_outline(pdf_path, poppler_path, output_path, line_tolerance=2, ocr_default_font_size=10):
    images = convert_from_path(pdf_path, poppler_path=poppler_path)

    all_lines = []
    toc_pages = set()

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = [table.bbox for table in page.find_tables()]
            lines_dict = defaultdict(list)

            if page.chars:
                for char in page.chars:
                    x0, y0, x1, y1 = char["x0"], char["top"], char["x1"], char["bottom"]
                    if inside_table(x0, y0, x1, y1, tables):
                        continue
                    top = round(char["top"] / line_tolerance) * line_tolerance
                    lines_dict[top].append(char)

                extracted_lines = []
                for top in sorted(lines_dict.keys()):
                    line_chars = sorted(lines_dict[top], key=lambda c: c["x0"])
                    line_text = "".join(c["text"] for c in line_chars).strip()
                    if line_text:
                        extracted_lines.append(line_text)

                if is_toc_page(extracted_lines):
                    toc_pages.add(page_number)

                for top in sorted(lines_dict.keys()):
                    line_chars = sorted(lines_dict[top], key=lambda c: c["x0"])
                    line_text = "".join(c["text"] for c in line_chars).strip()
                    if not line_text:
                        continue
                    font_sizes = [c["size"] for c in line_chars]
                    avg_font_size = round(sum(font_sizes) / len(font_sizes), 2)
                    all_lines.append({
                        "text": line_text,
                        "font_size": avg_font_size,
                        "page": page_number,
                        "top": top
                    })

            else:  # OCR fallback
                ocr_text = pytesseract.image_to_string(images[page_number - 1])
                extracted_lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
                if is_toc_page(extracted_lines):
                    toc_pages.add(page_number)
                for line in extracted_lines:
                    all_lines.append({
                        "text": line,
                        "font_size": ocr_default_font_size,
                        "page": page_number,
                        "top": None
                    })

    unique_sizes = sorted({line["font_size"] for line in all_lines}, reverse=True)
    title_size = unique_sizes[0] if unique_sizes else None
    title_parts = [line["text"] for line in all_lines if line["font_size"] == title_size and line["page"] <= 2]

    font_to_heading = {}
    if len(unique_sizes) > 1:
        font_to_heading[unique_sizes[1]] = "H1"
    if len(unique_sizes) > 2:
        font_to_heading[unique_sizes[2]] = "H2"
    if len(unique_sizes) > 3:
        font_to_heading[unique_sizes[3]] = "H3"

    outline = []
    seen = set()

    for line in all_lines:
        text = clean_text(line["text"])
        is_toc = line["page"] in toc_pages

        if should_skip(text, is_toc=is_toc):
            continue

        level = detect_numbering_level(text)
        if not level:
            level = font_to_heading.get(line["font_size"])

        if level in {"H1", "H2", "H3"} and text not in seen:
            outline.append({
                "level": level,
                "text": text,
                "page": line["page"]
            })
            seen.add(text)

    result = {
        "title": " ".join(title_parts).strip(),
        "outline": outline
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

# ---------------- Batch PDF Runner ----------------
def process_all_pdfs(input_dir, output_dir, poppler_path, line_tolerance, ocr_default_font_size):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            input_pdf = os.path.join(input_dir, filename)
            output_json = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.json")
            try:
                extract_outline(
                    pdf_path=input_pdf,
                    poppler_path=poppler_path,
                    output_path=output_json,
                    line_tolerance=line_tolerance,
                    ocr_default_font_size=ocr_default_font_size
                )
            except Exception as e:
                print(f"Failed to process {filename}: {e}")

# ---------------- CLI Support ----------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract outlines from all PDFs in a folder")
    parser.add_argument("--input", required=True, help="Input folder containing PDFs")
    parser.add_argument("--output", required=True, help="Output folder to save JSONs")
    parser.add_argument("--poppler", required=True, help="Path to poppler binary directory")
    parser.add_argument("--tolerance", type=int, default=DEFAULT_LINE_TOLERANCE, help="Line tolerance value")
    parser.add_argument("--ocr_font", type=int, default=DEFAULT_OCR_FONT_SIZE, help="Default OCR font size")

    args = parser.parse_args()

    process_all_pdfs(
        input_dir=args.input,
        output_dir=args.output,
        poppler_path=args.poppler,
        line_tolerance=args.tolerance,
        ocr_default_font_size=args.ocr_font
    )
