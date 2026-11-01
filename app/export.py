from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether


def timestamp(seconds, milliseconds=False):
    total = round(seconds * 1000)
    hours, rest = divmod(total, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, millis = divmod(rest, 1000)
    value = f"{hours:02}:{minutes:02}:{secs:02}"
    return value + f".{millis:03}" if milliseconds else value


def vtt(segments, language="en"):
    lines = ["WEBVTT", ""]
    for s in segments:
        text = (s.get("translation") or "") if language == "pt" else s["text"]
        if text:
            lines.extend([str(s["idx"]), f'{timestamp(s["start"], True)} --> {timestamp(s["end"], True)}', escape(text).replace("\n", " "), ""])
    return "\n".join(lines)


def pdf(movie, segments, language="bilingual"):
    font = "Helvetica"
    for path in [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]:
        if path.exists():
            if "Studio" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("Studio", str(path)))
            font = "Studio"
            break
    styles = getSampleStyleSheet()
    title = ParagraphStyle("StudioTitle", fontName=font, fontSize=23, leading=29, textColor=colors.HexColor("#164c3c"), spaceAfter=12)
    body = ParagraphStyle("StudioBody", fontName=font, fontSize=10, leading=15, spaceAfter=7, alignment=TA_LEFT, splitLongWords=True)
    muted = ParagraphStyle("StudioMuted", parent=body, fontSize=9, textColor=colors.HexColor("#66736b"))
    stamp = ParagraphStyle("StudioTime", parent=muted, spaceBefore=12, spaceAfter=5)
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=(210*mm, 297*mm), rightMargin=22*mm, leftMargin=22*mm, topMargin=22*mm, bottomMargin=23*mm,
                            title=movie["title"], author="English Studio")
    labels = {"en": "Diálogos em inglês", "pt": "Tradução em português brasileiro", "bilingual": "Diálogos em inglês e português brasileiro"}
    story = [Paragraph("ENGLISH STUDIO", muted), Paragraph(escape(movie["title"]), title), Paragraph(labels[language], body),
             Paragraph("Transcrição e tradução automáticas: revise possíveis imprecisões. As marcas de tempo acompanham o vídeo original.", muted), Spacer(1, 6*mm)]
    for s in segments:
        block = [Paragraph(f'{timestamp(s["start"])} - {timestamp(s["end"])}', stamp)]
        if language in ("en", "bilingual"):
            block.append(Paragraph(escape(s["text"]), body))
        if language in ("pt", "bilingual"):
            block.append(Paragraph(escape(s.get("translation") or ""), muted if language == "bilingual" else body))
        # Very long edited speeches must be able to split across pages.
        if len(s["text"]) + len(s.get("translation") or "") < 1400:
            story.append(KeepTogether(block))
        else:
            story.extend(block)

    def footer(canvas, document):
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#66736b"))
        canvas.drawString(22*mm, 13*mm, "English Studio | Seu cinema. Seu inglês.")
        canvas.drawRightString(188*mm, 13*mm, str(document.page))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
