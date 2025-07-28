import os
import re
import json
import pytesseract
import pdfplumber
from pdf2image import convert_from_path
from collections import defaultdict

# ---------------- Settings ----------------
input_folder = "input"
output_folder = "output"
poppler_path = r"C:\Users\anike\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"
line_tolerance = 2
ocr_default_font_size = 10

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
    text = re.sub(r'\.{2,}', '', text)  # remove dotted leaders
    text = re.sub(r'\s+\d+$', '', text)  # remove trailing page numbers
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
def extract_outline(pdf_path):
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

    return {
        "title": " ".join(title_parts).strip(),
        "outline": outline
    }

# ---------------- Batch Processor ----------------
def process_all_pdfs():
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for file in os.listdir(input_folder):
        if file.lower().endswith(".pdf"):
            pdf_path = os.path.join(input_folder, file)
            result = extract_outline(pdf_path)
            output_file = os.path.join(output_folder, os.path.splitext(file)[0] + ".json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)

# ---------------- Run ----------------
if __name__ == "__main__":
    process_all_pdfs()
