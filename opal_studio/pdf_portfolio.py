"""
Opal - Acrobat-Grade PDF Portfolio & Package Engine
Plain English: Bundles multiple files into a single master PDF document with
custom schemas, metadata, and an executive cover page (ISO 32000-1 § 12.3 Collections).
Enables viewing, extracting, and assembling multi-file packages completely offline.
"""

import os
import sys
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import fitz

class PortfolioError(Exception):
    """Raised when portfolio generation, inspection, or extraction fails."""
    pass


def _human_size(num_bytes: int) -> str:
    """Plain English: Formats raw bytes into human-readable units (KB, MB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def is_portfolio(pdf_path: str) -> bool:
    """
    Plain English: Checks whether the given PDF has an ISO 32000-1 Collection dictionary,
    marking it as an Adobe Acrobat PDF Portfolio.
    """
    if not os.path.isfile(pdf_path):
        return False
    try:
        doc = fitz.open(pdf_path)
        try:
            cat_xref = doc.pdf_catalog()
            if not cat_xref:
                return False
            key_type, val = doc.xref_get_key(cat_xref, "Collection")
            return key_type in ("dict", "xref") and bool(val) and val != "null"
        finally:
            doc.close()
    except Exception:
        return False


def get_portfolio_info(pdf_path: str) -> Dict[str, Any]:
    """
    Plain English: Reads the portfolio file manifest, schema, and embedded attachments.
    """
    if not os.path.isfile(pdf_path):
        raise PortfolioError(f"PDF file not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    try:
        cat_xref = doc.pdf_catalog()
        has_collection = False
        default_doc = ""
        view_mode = "details"
        if cat_xref:
            ktype, val = doc.xref_get_key(cat_xref, "Collection")
            if ktype in ("dict", "xref") and val and val != "null":
                has_collection = True
                if "/View /T" in val:
                    view_mode = "tile"
                # Check default doc if specified
                if "/D (" in val:
                    try:
                        d_start = val.find("/D (") + 4
                        d_end = val.find(")", d_start)
                        default_doc = val[d_start:d_end]
                    except Exception:
                        pass

        names = list(doc.embfile_names() or [])
        files = []
        total_size = 0

        for name in names:
            info = doc.embfile_info(name) or {}
            size = info.get("size") or info.get("length") or 0
            total_size += size
            filename = info.get("filename") or info.get("ufilename") or name
            desc = info.get("description") or ""
            ext = Path(filename).suffix.lower()
            mime, _ = mimetypes.guess_type(filename)

            files.append({
                "name": name,
                "filename": filename,
                "size": size,
                "size_human": _human_size(size),
                "description": desc,
                "extension": ext,
                "mime_type": mime or "application/octet-stream",
                "creation_date": str(info.get("creationDate") or ""),
                "mod_date": str(info.get("modDate") or ""),
            })

        return {
            "is_portfolio": has_collection,
            "has_embedded_files": bool(names),
            "files_count": len(files),
            "total_size_bytes": total_size,
            "total_size_human": _human_size(total_size),
            "view_mode": view_mode,
            "default_file": default_doc,
            "files": files,
        }
    finally:
        doc.close()


def _draw_portfolio_cover_page(page: fitz.Page, title: str, description: str,
                               files_meta: List[Dict[str, Any]]):
    """
    Plain English: Draws a polished, dark executive cover page seen in viewers
    that do not support interactive Portfolio UI panels.
    """
    # Background
    rect = fitz.Rect(0, 0, page.rect.width, page.rect.height)
    page.draw_rect(rect, color=(0.06, 0.08, 0.12), fill=(0.06, 0.08, 0.12))

    # Header Card
    card = fitz.Rect(40, 40, page.rect.width - 40, 160)
    page.draw_rect(card, color=(0.20, 0.24, 0.35), fill=(0.10, 0.13, 0.20), width=1.0)

    page.insert_text((60, 72), "OPAL PDF PORTFOLIO", fontsize=10, fontname="helv", color=(0.54, 0.51, 1.0))
    display_title = title if len(title) <= 45 else title[:42] + "..."
    page.insert_text((60, 102), display_title, fontsize=17, fontname="hebo", color=(0.95, 0.96, 0.98))

    desc_text = description or f"This portfolio package bundles {len(files_meta)} attached documents and data files."
    if len(desc_text) > 85:
        desc_text = desc_text[:82] + "..."
    page.insert_text((60, 132), desc_text, fontsize=10, fontname="helv", color=(0.70, 0.74, 0.82))

    # File listing container
    table_card = fitz.Rect(40, 180, page.rect.width - 40, page.rect.height - 70)
    page.draw_rect(table_card, color=(0.20, 0.24, 0.35), fill=(0.08, 0.10, 0.15), width=1.0)

    page.insert_text((60, 210), f"Packaged Contents ({len(files_meta)} files)", fontsize=12, fontname="hebo", color=(0.95, 0.96, 0.98))

    y = 245
    max_items = 8  # Show top items on cover page
    for idx, item in enumerate(files_meta[:max_items]):
        # Row card
        row_rect = fitz.Rect(55, y - 18, page.rect.width - 55, y + 22)
        page.draw_rect(row_rect, color=None, fill=(0.12, 0.15, 0.22))

        fn = item["filename"]
        if len(fn) > 38:
            fn = fn[:35] + "..."
        sz = item["size_human"]
        ext_label = item["extension"].upper().lstrip(".") or "FILE"

        page.insert_text((68, y), f"[{ext_label}] {fn}", fontsize=11, fontname="hebo", color=(0.40, 0.85, 0.65))
        page.insert_text((page.rect.width - 150, y), sz, fontsize=10, fontname="helv", color=(0.65, 0.70, 0.80))

        item_desc = item.get("description") or f"Embedded file format: {item.get('mime_type')}"
        if len(item_desc) > 65:
            item_desc = item_desc[:62] + "..."
        page.insert_text((68, y + 14), item_desc, fontsize=9, fontname="helv", color=(0.55, 0.60, 0.70))
        y += 48

    if len(files_meta) > max_items:
        rem = len(files_meta) - max_items
        page.insert_text((68, y + 10), f"+ {rem} additional files in portfolio", fontsize=10, fontname="helv", color=(0.60, 0.65, 0.75))

    # Instructions footer
    page.insert_text(
        (60, page.rect.height - 45),
        "For the best experience, open this PDF Portfolio in Opal Studio or Adobe Acrobat to navigate and extract files.",
        fontsize=9,
        fontname="helv",
        color=(0.50, 0.55, 0.65)
    )


def create_portfolio(files: List[Union[str, Path, Dict[str, Any]]],
                     dst_pdf: str,
                     title: str = "Opal Document Portfolio",
                     description: str = "",
                     default_view: str = "details") -> Dict[str, Any]:
    """
    Plain English: Assembles multiple files into a single master PDF Portfolio with
    an executive cover page and ISO 32000-1 Collection dictionaries.
    """
    if not files:
        raise PortfolioError("At least one file must be provided to create a portfolio.")

    doc = fitz.open()
    # Add standardized US Letter cover page (612 x 792)
    cover_page = doc.new_page(width=612, height=792)

    prepared_meta = []
    default_doc_name = ""

    for item in files:
        if isinstance(item, (str, Path)):
            src_path = Path(item)
            if not src_path.exists():
                raise PortfolioError(f"Input file not found: {src_path}")
            name = src_path.name
            desc = ""
            data = src_path.read_bytes()
        elif isinstance(item, dict):
            src_path = Path(item["path"]) if "path" in item else None
            name = item.get("name") or (src_path.name if src_path else "attachment.dat")
            desc = item.get("description", "")
            if "data" in item and isinstance(item["data"], (bytes, bytearray)):
                data = bytes(item["data"])
            elif src_path and src_path.exists():
                data = src_path.read_bytes()
            else:
                raise PortfolioError(f"File data or valid path required for item {name}")
        else:
            continue

        if not default_doc_name:
            default_doc_name = name

        doc.embfile_add(name, data, filename=name, desc=desc)
        ext = Path(name).suffix.lower()
        mime, _ = mimetypes.guess_type(name)
        prepared_meta.append({
            "name": name,
            "filename": name,
            "size": len(data),
            "size_human": _human_size(len(data)),
            "description": desc,
            "extension": ext,
            "mime_type": mime or "application/octet-stream",
        })

    # Render cover page
    _draw_portfolio_cover_page(cover_page, title, description, prepared_meta)

    # Intersperse ISO 32000-1 /Collection dictionary
    cat_xref = doc.pdf_catalog()
    view_code = "/T" if default_view == "tile" else "/D"
    escaped_def = default_doc_name.replace("(", "\\(").replace(")", "\\)")

    # Standard Acrobat Collection Schema: Name, Desc, Size, ModDate
    collection_dict_str = f"""<<
  /Type /Collection
  /View {view_code}
  /D ({escaped_def})
  /Schema <<
    /Name << /Type /Text /N (File Name) /O 1 >>
    /Size << /Type /Number /N (Size) /O 2 >>
    /Desc << /Type /Text /N (Description) /O 3 >>
    /ModDate << /Type /Date /N (Modified) /O 4 >>
  >>
  /Sort <<
    /S /Name
    /A true
  >>
>>"""

    doc.xref_set_key(cat_xref, "Collection", collection_dict_str)

    target = Path(dst_pdf)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(target), garbage=3, deflate=True)
    doc.close()

    return {
        "success": True,
        "output_path": str(target),
        "files_count": len(prepared_meta),
        "total_size_bytes": sum(m["size"] for m in prepared_meta),
        "total_size_human": _human_size(sum(m["size"] for m in prepared_meta)),
    }


def extract_portfolio_file(pdf_path: str, file_name: str, dst_path: str) -> str:
    """
    Plain English: Extracts a single file by name from the PDF portfolio.
    """
    if not os.path.isfile(pdf_path):
        raise PortfolioError(f"PDF file not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    try:
        names = doc.embfile_names() or []
        if file_name not in names:
            raise PortfolioError(f"File '{file_name}' not found in portfolio. Available: {names}")
        data = doc.embfile_get(file_name)
        target = Path(dst_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)
    finally:
        doc.close()


def extract_all_portfolio_files(pdf_path: str, dst_folder: str) -> List[str]:
    """
    Plain English: Extracts every packaged file inside the portfolio into the target directory.
    """
    if not os.path.isfile(pdf_path):
        raise PortfolioError(f"PDF file not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    try:
        names = doc.embfile_names() or []
        out_dir = Path(dst_folder)
        out_dir.mkdir(parents=True, exist_ok=True)
        extracted = []
        for name in names:
            try:
                info = doc.embfile_info(name) or {}
                fn = info.get("filename") or info.get("ufilename") or name
                target = out_dir / Path(fn).name
                data = doc.embfile_get(name)
                target.write_bytes(data)
                extracted.append(str(target))
            except Exception as e:
                continue
        return extracted
    finally:
        doc.close()


def add_file_to_portfolio(pdf_path: str, file_to_add: str,
                          description: str = "",
                          dst_pdf: Optional[str] = None) -> Dict[str, Any]:
    """
    Plain English: Adds an additional file into an existing PDF portfolio.
    """
    if not os.path.isfile(pdf_path):
        raise PortfolioError(f"Portfolio PDF not found: {pdf_path}")
    source_file = Path(file_to_add)
    if not source_file.is_file():
        raise PortfolioError(f"File to attach not found: {source_file}")

    target = dst_pdf or pdf_path
    doc = fitz.open(pdf_path)
    try:
        name = source_file.name
        data = source_file.read_bytes()
        doc.embfile_add(name, data, filename=name, desc=description)

        # Ensure Collection dictionary exists
        cat_xref = doc.pdf_catalog()
        ktype, val = doc.xref_get_key(cat_xref, "Collection")
        if ktype not in ("dict", "xref") or not val or val == "null":
            escaped_name = name.replace("(", "\\(").replace(")", "\\)")
            doc.xref_set_key(cat_xref, "Collection", f"<< /Type /Collection /View /D /D ({escaped_name}) >>")

        if target == pdf_path:
            doc.saveIncr()
        else:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            doc.save(target, garbage=3, deflate=True)
    finally:
        doc.close()

    return get_portfolio_info(target)


def remove_file_from_portfolio(pdf_path: str, file_name: str,
                               dst_pdf: Optional[str] = None) -> Dict[str, Any]:
    """
    Plain English: Removes an attached file from an existing PDF portfolio.
    """
    if not os.path.isfile(pdf_path):
        raise PortfolioError(f"Portfolio PDF not found: {pdf_path}")

    target = dst_pdf or pdf_path
    doc = fitz.open(pdf_path)
    try:
        names = doc.embfile_names() or []
        if file_name not in names:
            raise PortfolioError(f"File '{file_name}' not found in portfolio.")

        remaining = []
        for name in names:
            if name == file_name:
                continue
            info = doc.embfile_info(name)
            data = doc.embfile_get(name)
            remaining.append((name, data, info.get("filename", name), info.get("description", "")))

        # Reset EmbeddedFiles in catalog cleanly to avoid single-item array shift bug
        cat_xref = doc.pdf_catalog()
        doc.xref_set_key(cat_xref, "Names", "<< >>")

        # Re-add remaining files
        for name, data, fn, desc in remaining:
            doc.embfile_add(name, data, filename=fn, desc=desc)

        if remaining:
            new_def = remaining[0][0].replace("(", "\\(").replace(")", "\\)")
            doc.xref_set_key(cat_xref, "Collection", f"<< /Type /Collection /View /D /D ({new_def}) >>")

        if target == pdf_path:
            doc.saveIncr()
        else:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            doc.save(target, garbage=3, deflate=True)
    finally:
        doc.close()

    return get_portfolio_info(target)
