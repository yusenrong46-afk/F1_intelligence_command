"""Write a tiny multi-page PDF with plain Helvetica text (test fixture helper)."""
import sys

def make_pdf(pages):
    objs = []
    font_id = 3
    kids = []
    content_ids = []
    n = 4
    page_objs = []
    for text_lines in pages:
        stream = "BT /F1 11 Tf 72 720 Td 14 TL " + " ".join(f"({l.replace('(', '[').replace(')', ']')}) Tj T*" for l in text_lines) + " ET"
        content_id, page_id = n, n + 1
        n += 2
        page_objs.append((page_id, content_id, stream))
        kids.append(page_id)
    out = ["%PDF-1.4"]
    offsets = {}
    body = []
    def add(i, s):
        body.append((i, s))
    add(1, "<< /Type /Catalog /Pages 2 0 R >>")
    add(2, f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>")
    add(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for page_id, content_id, stream in page_objs:
        add(content_id, f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        add(page_id, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R >> >> >>")
    body.sort()
    data = "%PDF-1.4\n"
    for i, s in body:
        offsets[i] = len(data.encode())
        data += f"{i} 0 obj\n{s}\nendobj\n"
    xref = len(data.encode())
    total = max(offsets) + 1
    data += f"xref\n0 {total}\n0000000000 65535 f \n" + "".join(f"{offsets[i]:010d} 00000 n \n" for i in range(1, total))
    data += f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return data.encode()
