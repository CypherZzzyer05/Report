"""Render the feasibility Markdown to HTML and a paginated Chinese PDF."""
import argparse
import html
from pathlib import Path
import re
from urllib.parse import quote

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, LongTable, PageBreak, Paragraph,
                               SimpleDocTemplate, Spacer, TableStyle)


def normalize(text):
    return (text.replace('–', '-').replace('—', '-').replace('−', '-')
            .replace('⁻⁸', '^-8').replace('⁻⁷', '^-7').replace('⁻⁶', '^-6')
            .replace('⁻¹⁵', '^-15').replace('²', '^2')
            .translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')))


def rich(text):
    text = html.escape(normalize(text))
    def link(match):
        target = match[2].replace('&amp;', '&')
        if not target.startswith(('https://', 'http://')):
            repo = Path(__file__).resolve().parents[1]
            folder = repo/'reports/2026-10-18_device_feasibility'
            relative = (folder/target).resolve().relative_to(repo).as_posix()
            target = 'https://github.com/CypherZzzyer05/Report/blob/main/'+quote(relative)
        return '<link href="'+html.escape(target, quote=True)+'" color="#1768ac">'+match[1]+'</link>'
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    return text.replace('`', '')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--font', type=Path, required=True)
    parser.add_argument('--bold-font', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = root/'reports/2026-10-18_device_feasibility'
    output = root/'output/pdf/device_feasibility_2026-10-18.pdf'
    output.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont('YaHei', str(args.font)))
    pdfmetrics.registerFont(TTFont('YaHeiBold', str(args.bold_font)))
    pdfmetrics.registerFontFamily('YaHei', normal='YaHei', bold='YaHeiBold', italic='YaHei', boldItalic='YaHeiBold')
    styles = getSampleStyleSheet()
    common = dict(fontName='YaHei', wordWrap='CJK', textColor=colors.HexColor('#233044'), alignment=TA_LEFT)
    body = ParagraphStyle('CNBody', fontSize=9.3, leading=15.6, spaceAfter=7, **common)
    title = ParagraphStyle('CNTitle', fontName='YaHeiBold', fontSize=21, leading=30,
                           spaceAfter=16, textColor=colors.HexColor('#163f61'), wordWrap='CJK')
    h2 = ParagraphStyle('CNH2', fontName='YaHeiBold', fontSize=14, leading=21,
                       spaceBefore=13, spaceAfter=8, keepWithNext=True, textColor=colors.HexColor('#163f61'), wordWrap='CJK')
    h3 = ParagraphStyle('CNH3', fontName='YaHeiBold', fontSize=10.7, leading=17,
                       spaceBefore=8, spaceAfter=6, keepWithNext=True, textColor=colors.HexColor('#163f61'), wordWrap='CJK')
    small = ParagraphStyle('CNSmall', parent=body, fontSize=8.0, leading=13, spaceAfter=5)
    table_body = ParagraphStyle('CNTable', parent=body, fontSize=8, leading=13, spaceAfter=0)
    table_head = ParagraphStyle('CNTableHead', parent=table_body, fontName='YaHeiBold', textColor=colors.HexColor('#163f61'))
    warn = ParagraphStyle('CNWarn', parent=body, backColor=colors.HexColor('#fff1e9'), borderColor=colors.HexColor('#c47a50'),
                          borderWidth=.6, borderPadding=9, spaceBefore=7, spaceAfter=13)
    bullet = ParagraphStyle('CNBullet', parent=body, leftIndent=10, firstLineIndent=-8)
    width = A4[0]-104
    story = []
    lines = (report/'README.md').read_text(encoding='utf-8').splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1; continue
        if line == '<!-- PAGEBREAK -->':
            story.append(PageBreak()); index += 1; continue
        if line.startswith('!['):
            match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            if match:
                image = Image(str(report/match[2]))
                scale = min(width/image.imageWidth, 238/image.imageHeight)
                image.drawWidth, image.drawHeight = image.imageWidth*scale, image.imageHeight*scale
                story.extend([Spacer(1, 5), image, Spacer(1, 10)])
                index += 1; continue
        if line.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                cells = [x.strip() for x in lines[index].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+', x) for x in cells):
                    rows.append(cells)
                index += 1
            count = len(rows[0])
            weights = {2:[.48,.52], 3:[.23,.37,.40], 4:[.18,.25,.27,.30]}.get(count, [1/count]*count)
            if '原始 n / k' in rows[0]: weights = [.14,.27,.29,.30]
            cells = [[Paragraph(rich(c), table_head if i == 0 else table_body) for c in row]
                     for i, row in enumerate(rows)]
            table = LongTable(cells, colWidths=[width*x for x in weights], repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf1f7')),
                                       ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#d2dde6')),
                                       ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),
                                       ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),
                                       ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
            story.extend([table, Spacer(1, 10)]); continue
        if line.startswith('# '):
            story.append(Paragraph(rich(line[2:]), title)); index += 1; continue
        if line.startswith('## '):
            story.append(Paragraph(rich(line[3:]), h2)); index += 1; continue
        if line.startswith('### '):
            story.append(Paragraph(rich(line[4:]), h3)); index += 1; continue
        if line.startswith('> '):
            story.append(Paragraph(rich(line[2:]), warn)); index += 1; continue
        if line.startswith('- '):
            style = small if line.startswith('- **S') else bullet
            story.append(Paragraph('• '+rich(line[2:]), style)); index += 1; continue
        parts = [line]; index += 1
        while index < len(lines) and lines[index].strip() and not lines[index].startswith(('#', '|', '!', '-', '>', '<!--')):
            parts.append(lines[index].strip()); index += 1
        story.append(Paragraph(rich(' '.join(parts)), body))

    def page(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#194e77')); canvas.setLineWidth(1)
        canvas.line(52, A4[1]-38, A4[0]-52, A4[1]-38)
        canvas.setFont('YaHei', 8); canvas.setFillColor(colors.HexColor('#52697c'))
        canvas.drawString(52, A4[1]-29, 'As2Se3 / Au 四聚体 | 技术与加工可行性')
        canvas.drawRightString(A4[0]-52, A4[1]-29, '2026-10-18')
        canvas.drawString(52, 27, '文献调研 + 原生材料只读复核 + 几何审查；非投片认证')
        canvas.drawRightString(A4[0]-52, 27, str(document.page))
        canvas.restoreState()

    document = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=52, rightMargin=52,
                                 topMargin=55, bottomMargin=45,
                                 title='As2Se3 / Au tetramer feasibility and manufacturability',
                                 author='Optics design research report')
    document.build(story, onFirstPage=page, onLaterPages=page)
    print(output)


if __name__ == '__main__':
    main()
