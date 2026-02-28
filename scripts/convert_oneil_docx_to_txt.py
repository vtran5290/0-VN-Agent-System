from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree.ElementTree import fromstring


WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_text_from_docx(docx_path: Path) -> str:
    """Extract plain text from a .docx file using only the Python standard library."""
    with zipfile.ZipFile(docx_path) as zf:
        with zf.open("word/document.xml") as doc_xml:
            xml_bytes = doc_xml.read()

    root = fromstring(xml_bytes)

    paragraphs: list[str] = []
    for para in root.iter(WORD_NAMESPACE + "p"):
        texts: list[str] = []
        for node in para.iter(WORD_NAMESPACE + "t"):
            if node.text:
                texts.append(node.text)

        if texts:
            paragraphs.append("".join(texts).strip())

    return "\n".join(p for p in paragraphs if p)


def main() -> None:
    # Source .docx outside the repo (user's Calibre library)
    source_path = Path(
        r"C:\Users\LOLII\Calibre Library\William J. O'Neil\How to Make Money in Stocks (2)\How to Make Money in Stocks - William J. O'Neil.docx"
    )

    # Output location inside this repo so the agent can read it
    output_path = Path("data/raw/oneil.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    text = extract_text_from_docx(source_path)
    output_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

