"""Publish the readable HTML, reference ledger and validation metadata."""
import hashlib
import json
from pathlib import Path
import re

import markdown

root = Path(__file__).resolve().parents[1]
folder = root/'reports/2026-10-18_device_feasibility'
text = (folder/'README.md').read_text(encoding='utf-8')
body = markdown.markdown(text, extensions=['tables', 'fenced_code'])
style = '''body{max-width:1100px;margin:36px auto;padding:0 24px;font:16px/1.8 'Microsoft YaHei',sans-serif;color:#233044}
h1{font-size:29px;line-height:1.4}h2{margin-top:2em;border-bottom:1px solid #d5e0e9;padding-bottom:.3em;font-size:23px}
h3{font-size:19px}img{display:block;width:100%;height:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px;margin:18px 0}
td,th{border:1px solid #d5dfe7;padding:9px;text-align:left}th{background:#eaf1f7}blockquote{background:#fff1e9;border-left:4px solid #bb7049;padding:10px 18px;margin:20px 0}
code{font-family:Consolas,monospace}a{color:#1768ac}strong{color:#133f60}@media(max-width:650px){body{padding:0 14px;font-size:15px}table{display:block;overflow-x:auto}h1{font-size:24px}}
@media print{body{margin:0;font-size:11pt}h2{break-after:avoid}img{break-inside:avoid}}'''
html = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>器件可行性与可加工性调研</title><style>'+style+'</style><body>'+body+'</body></html>\n'
(folder/'index.html').write_text(html, encoding='utf-8', newline='\n')
types = {'S01':'official_solver_documentation', 'S02':'official_solver_documentation', 'S03':'author_supplied_material_data',
         'S04':'original_research', 'S05':'original_experiment', 'S06':'original_experiment', 'S07':'analogous_structure_experiment',
         'S08':'analogous_structure_numerical_study', 'S09':'official_solver_documentation', 'S10':'official_solver_documentation',
         'S11':'same_material_layer_stack_experiment', 'S12':'same_material_etching_experiment', 'S13':'same_material_imprinting_experiment',
         'S14':'author_material_deposition_technical_paper', 'S15':'same_material_stability_experiment', 'S16':'manufacturer_SDS'}
sources = []
for line in text.splitlines():
    match = re.match(r'- \*\*(S\d+) · (.*?)\*\* (.*)', line)
    if match:
        sources.append(dict(id=match[1], reference=match[2], scope_note=match[3],
                            evidence_type=types[match[1]], urls=re.findall(r'\]\((https?://[^)]+)\)', line)))
assert len(sources) == 16
(folder/'data/sources.json').write_text(json.dumps(dict(checked_on='2026-10-18',sources=sources), ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
old = root/'reports/2026-10-18_topmetal_thick_substrate/index.html'
old_html = old.read_text(encoding='utf-8')
warning = '<blockquote style="background:#fff1e9;padding:14px;border-left:4px solid #bb7049"><strong>材料审核更正（2026-10-18）：</strong>已保存本机 FSP 的 Au 拟合几乎丢失 Palik 输入损耗。原始谱线保留，不作为真实器件性能认证。<a href="../2026-10-18_device_feasibility/index.html">阅读新调研与原生复核</a>；服务器当前任务仍需核查。</blockquote>'
if 'material-fit-erratum' not in old_html:
    old.write_text(old_html.replace('<body>', '<body>'+warning, 1), encoding='utf-8', newline='\n')
for path in folder.rglob('*.json'):
    if path.name != 'checksums.json':
        path.write_text(path.read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
checksums = {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'checksums.json'}
pdf = root/'output/pdf/device_feasibility_2026-10-18.pdf'
checksums[str(pdf.relative_to(root)).replace('\\', '/')] = hashlib.sha256(pdf.read_bytes()).hexdigest()
(folder/'checksums.json').write_text(json.dumps(dict(files_sha256=checksums,
    scope='literature research, geometry-only calculations and read-only native material check',
    no_new_time_domain_solver_run=True, generator_modified=False, source_fsp_modified=False), indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(sources=len(sources), files_hashed=len(checksums), pdf_bytes=pdf.stat().st_size)))
