def extract_text_from_pdf(path: str) -> str:
    """
    Extract text from PDF — handles all table formats generically.
    
    Key behaviors:
    - Multiline table cells are split into individual lines
      so each "Label: Value" pair is on its own line
    - 2-column table rows use " => " separator
    - All other rows are joined with spaces
    - Page text is appended after table text
    """
    import pdfplumber
    pages_text = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            table_lines = []

            for table in page.extract_tables():
                for row in table:
                    # Clean each cell — strip whitespace
                    cells = []
                    for cell in row:
                        if cell:
                            # Split multiline cells and clean each subline
                            sublines = [
                                " ".join(sub.split())
                                for sub in cell.split("\n")
                                if sub.strip()
                            ]
                            cells.append(sublines)
                        else:
                            cells.append([])

                    # 2-column row: expand each subline pair
                    if len(cells) == 2:
                        left_lines  = cells[0]
                        right_lines = cells[1]

                        # First expand left cell lines as individual lines
                        # (catches multiline header like "SOW ID: X\nDate: Y")
                        for subline in left_lines:
                            table_lines.append(subline)

                        # If right cell also has content, expand those too
                        for subline in right_lines:
                            table_lines.append(subline)

                        # Also add the classic "Label => Value" for single-line pairs
                        if len(left_lines) == 1 and len(right_lines) == 1:
                            lbl = left_lines[0]
                            val = right_lines[0]
                            if lbl and val:
                                table_lines.append(f"{lbl} => {val}")

                    else:
                        # Multi-column or single-column: flatten all cells
                        flat = []
                        for cell_lines in cells:
                            flat.extend(cell_lines)
                        if flat:
                            table_lines.append("  ".join(flat))

            # Get page raw text
            t = page.extract_text(x_tolerance=3, layout=True)

            combined = ""
            if table_lines:
                combined += "\n".join(table_lines) + "\n"
            if t and t.strip():
                combined += t.strip()

            if combined.strip():
                pages_text.append(combined.strip())

    text = "\n".join(pages_text)
    print(f"  {len(pages_text)} pages, {len(text):,} chars extracted")
    return text