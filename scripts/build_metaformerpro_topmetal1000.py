"""Render the archived MetaformerPro report as a self-contained offline page."""
from pathlib import Path

import markdown


root = Path(__file__).resolve().parents[1]
folder = root / 'reports/2026-10-24_metaformerpro_topmetal1000'
body = markdown.markdown((folder / 'README.md').read_text(encoding='utf-8'),
                         extensions=['tables', 'fenced_code'])
style = '''
body{max-width:1100px;margin:36px auto;padding:0 24px;font:16px/1.8 'Microsoft YaHei',sans-serif;color:#233044}
h1{font-size:29px;line-height:1.4}h2{margin-top:2em;border-bottom:1px solid #d5e0e9;padding-bottom:.3em;font-size:23px}
img{display:block;width:100%;height:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px;margin:18px 0}
td,th{border:1px solid #d5dfe7;padding:9px;text-align:left}th{background:#eaf1f7}
code{font-family:Consolas,monospace;overflow-wrap:anywhere}pre{background:#f2f5f8;padding:16px;overflow:auto}
pre code{overflow-wrap:normal}a{color:#1768ac}strong{color:#133f60}
footer{margin-top:36px;border-top:1px solid #d5e0e9;padding-top:16px;font-size:14px}
@media(max-width:650px){body{padding:0 14px;font-size:15px}table{display:block;overflow-x:auto}h1{font-size:24px}}
@media print{body{margin:0;font-size:11pt}h2{break-after:avoid}img{break-inside:avoid}}
'''
footer = '''<footer><p><a href="README.md">Markdown 原文</a> ·
<a href="summary.json">训练汇总</a> · <a href="selection.json">冻结选择</a> ·
<a href="test_metrics.json">逐次测试指标</a> · <a href="verification.json">重载与身份核验</a> ·
<a href="prediction_207.json">演示结构参数</a></p>
<p><a href="https://github.com/CypherZzzyer05/Optics_design/tree/35af85b/Metaformer_As2Se3">本轮模型代码、配置、数据与部署权重（35af85b）</a></p>
<p><a href="../../README.md">报告仓库目录</a></p></footer>'''
html = ('<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>MetaformerPro：新层序1000样本训练与验证</title>'
        f'<style>{style}</style></head><body>{body}{footer}</body></html>\n')
(folder / 'index.html').write_text(html, encoding='utf-8', newline='\n')
print(folder / 'index.html')
