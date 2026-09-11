#!/usr/bin/env python3
"""
Build the Mishkaat scientific & engineering report as a PDF.

Two passes: the first renders the document so that the table of contents can be
told which page each chapter actually starts on; the second renders it again
with those numbers filled in. The table of contents does not change length
between passes, so the numbers stay correct.

    pip install playwright pypdf
    python docs/report/build.py

Chromium is located at $CHROMIUM_PATH, or /opt/pw-browsers/chromium, or the
Playwright default.
"""
import asyncio
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARTS = HERE / "parts"
HTML = HERE / "mishkaat-report.html"
PDF = HERE / "Mishkaat_Engineering_Report.pdf"

# data-find attribute in the TOC -> the heading text as it appears once rendered
TOC_TARGETS = {
    "CHAPTER 1": "Chapter 1 Introduction",
    "CHAPTER 2": "Chapter 2 Scope, Assumptions and Delimitations",
    "CHAPTER 3": "Chapter 3 Stakeholders and Users",
    "CHAPTER 4": "Chapter 4 Requirements Specification",
    "CHAPTER 5": "Chapter 5 System Architecture",
    "CHAPTER 6": "Chapter 6 Technology Stack",
    "CHAPTER 7": "Chapter 7 Database Design and Data Dictionary",
    "CHAPTER 8": "Chapter 8 API Specification",
    "CHAPTER 9": "Chapter 9 The Analytical Engine",
    "CHAPTER 10": "Chapter 10 Security Engineering",
    "CHAPTER 11": "Chapter 11 Business Workflows",
    "CHAPTER 12": "Chapter 12 User Interface and Interaction Design",
    "CHAPTER 13": "Chapter 13 Verification and Quality Assurance",
    "CHAPTER 14": "Chapter 14 Deployment and Operations",
    "CHAPTER 15": "Chapter 15 Project Metrics and Development History",
    "CHAPTER 16": "Chapter 16 Evaluation, Limitations and Future Work",
    "CHAPTER 17": "Chapter 17 Conclusion",
    "References and Sources": "Back Matter References and Sources",
    "Appendix A": "Appendix A Environment Variable Reference",
}

FOOTER = (
    '<div style="width:100%;font-size:8pt;color:#7b8794;'
    'font-family:Georgia,serif;padding:0 16mm;display:flex;'
    'justify-content:space-between;">'
    '<span>Mishkaat &mdash; Scientific &amp; Engineering Report</span>'
    '<span class="pageNumber"></span></div>'
)


def assemble() -> str:
    """Concatenate the numbered part files into one document."""
    parts = sorted(PARTS.glob("*.html"))
    if not parts:
        sys.exit(f"no part files found in {PARTS}")
    doc = "\n".join(p.read_text(encoding="utf-8") for p in parts)
    HTML.write_text(doc, encoding="utf-8")
    print(f"assembled {len(parts)} parts -> {HTML.name} ({len(doc):,} bytes)")
    return doc


def chromium_path():
    for candidate in (os.environ.get("CHROMIUM_PATH"), "/opt/pw-browsers/chromium"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


async def render(src: Path, out: Path) -> None:
    from playwright.async_api import async_playwright

    exe = chromium_path()
    async with async_playwright() as p:
        launch = {"args": ["--no-sandbox"]}
        if exe:
            launch["executable_path"] = exe
        browser = await p.chromium.launch(**launch)
        page = await browser.new_page()
        await page.goto(src.as_uri(), wait_until="networkidle")
        await page.emulate_media(media="print")
        await page.pdf(
            path=str(out),
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=FOOTER,
            margin={"top": "16mm", "bottom": "16mm", "left": "18mm", "right": "18mm"},
        )
        await browser.close()


def norm(text: str) -> str:
    """Strip every space and fold case.

    Headings are rendered with letter-spacing and a text-transform, so the
    extracted text of "Chapter 1" reads "C H A P T E R 1". Removing whitespace
    entirely makes the comparison independent of both.
    """
    return re.sub(r"\s+", "", text or "").lower()


def extract_pages(pdf_path: Path):
    """Normalised text of every page. Empty list if no extractor is available."""
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(pdf_path))
        return [norm(doc[i].get_textpage().get_text_range()) for i in range(len(doc))]
    except Exception:
        pass
    try:
        from pypdf import PdfReader

        return [norm(p.extract_text()) for p in PdfReader(str(pdf_path)).pages]
    except Exception:
        return []


def page_numbers(pdf_path: Path) -> dict:
    """Map each TOC target to the 1-based page it first appears on."""
    pages = extract_pages(pdf_path)
    if not pages:
        print("no PDF text extractor available - contents will carry no page numbers")
        return {}
    found = {}
    for key, heading in TOC_TARGETS.items():
        needle = norm(heading)
        for i, text in enumerate(pages, start=1):
            if needle in text:
                found[key] = i
                break
        else:
            print(f"  ! heading not located: {needle}")
    print(f"located {len(found)}/{len(TOC_TARGETS)} headings across {len(pages)} pages")
    return found


def fill_toc(doc: str, numbers: dict) -> str:
    def repl(match):
        key = match.group(1)
        return f'<span class="pg" data-find="{key}">{numbers.get(key, "")}</span>'

    return re.sub(r'<span class="pg" data-find="([^"]+)"></span>', repl, doc)


def main() -> None:
    doc = assemble()
    print("pass 1: rendering to locate headings ...")
    asyncio.run(render(HTML, PDF))
    numbers = page_numbers(PDF)
    if numbers:
        HTML.write_text(fill_toc(doc, numbers), encoding="utf-8")
        print("pass 2: rendering with table-of-contents page numbers ...")
        asyncio.run(render(HTML, PDF))
    size = PDF.stat().st_size
    count = len(extract_pages(PDF))
    print(f"done: {PDF} - {count or '?'} pages, {size:,} bytes")


if __name__ == "__main__":
    main()
