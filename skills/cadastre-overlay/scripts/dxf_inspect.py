"""列出 DXF 各圖層、圖元種類、數量、範圍，以及文字樣式、圖層設定、TEXT 內容（找控制用的道路邊線、確認座標系統）。
用法：python dxf_inspect.py <測量圖.dxf> <輸出.txt>
輸出一律由程式寫成 UTF-8 檔（PowerShell 重導向會變亂碼）。"""
import sys, ezdxf
from collections import Counter, defaultdict
doc = ezdxf.readfile(sys.argv[1]); msp = doc.modelspace()
out = open(sys.argv[2], 'w', encoding='utf-8')
c = Counter((e.dxf.layer, e.dxftype()) for e in msp)
ext = defaultdict(lambda: [1e18, 1e18, -1e18, -1e18])
def pts(e):
    t = e.dxftype()
    if t == 'LINE': return [e.dxf.start, e.dxf.end]
    if t == 'LWPOLYLINE': return [(p[0], p[1]) for p in e.get_points('xy')]
    if t == 'POLYLINE': return [v.dxf.location for v in e.vertices]
    if t in ('INSERT', 'TEXT', 'MTEXT'): return [e.dxf.insert]
    if t == 'CIRCLE': return [e.dxf.center]
    return []
for e in msp:
    for p in pts(e):
        x = ext[e.dxf.layer]; x[0] = min(x[0], p[0]); x[1] = min(x[1], p[1]); x[2] = max(x[2], p[0]); x[3] = max(x[3], p[1])
for (l, t), n in sorted(c.items()):
    print(f'{l}\t{t}\t{n}\t' + ' '.join(f'{v:.1f}' for v in ext[l]), file=out)
print('styles', [(s.dxf.name, s.dxf.font, s.dxf.get('bigfont', '')) for s in doc.styles], file=out)
print('layers', [(l.dxf.name, l.dxf.color, l.dxf.linetype) for l in doc.layers], file=out)
print('insunits', doc.header.get('$INSUNITS'), 'ltscale', doc.header.get('$LTSCALE'), file=out)
for e in msp.query('TEXT'):
    print('TEXT', e.dxf.layer, e.dxf.style, round(e.dxf.height, 2), e.dxf.text, file=out)
