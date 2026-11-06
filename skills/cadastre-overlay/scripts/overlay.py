"""快速套繪檢查圖：測量圖（灰）＋各頁地籍線與地號（p1 紫、p2 藍…），直接用定位參數畫，不必先建 DXF。
用法：python overlay.py <dump資料夾> <測量圖.dxf> <reg.json> <輸出.png> <E0> <E1> <N0> <N1> <overlay_config.json>
用途：比較初值、自動配準、控制點修正前後的差異；控制點附近放大看地籍線與道路邊線、側溝是否吻合。"""
import sys, json, pathlib
import numpy as np, ezdxf
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import load_config, load_reg, xf, survey_lines
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
D = pathlib.Path(sys.argv[1]); dxf = sys.argv[2]; reg = load_reg(sys.argv[3])
out = sys.argv[4]; x0, x1, y0, y1 = map(float, sys.argv[5:9]); CFG = load_config(sys.argv[9])
PC = CFG['pdf']; LBL = PC.get('label_max_size_pt', 6); MINW = PC.get('min_line_width', 0.05)
res = json.loads((D / 'parsed.json').read_text(encoding='utf-8'))
fig, ax = plt.subplots(figsize=(12, 12 * (y1 - y0) / (x1 - x0) + 0.5), dpi=110)
doc = ezdxf.readfile(dxf)
for L, p in survey_lines(doc.modelspace(), set(CFG['survey'].get('skip_layers', [])), close_lw=False):
    ax.plot(*zip(*p), color='0.45' if L not in CFG['registration'].get('auto_extra_skip_layers', []) else '0.8', lw=0.7)
cyc = ['magenta', 'blue', 'green', 'orange', 'brown', 'teal']
for i, page in enumerate(reg):
    r = reg[page]; col = cyc[i % len(cyc)]
    for p in res[page]['paths']:
        if p['op'] != 'S' or p['lw'] < MINW: continue
        W = xf(p['pts'], r); ax.plot(W[:, 0], W[:, 1], color=col, lw=1.0)
    for t in res[page]['texts']:
        if t['size'] < LBL:
            W = xf([(t['x'], t['y'])], r)[0]
            if x0 <= W[0] <= x1 and y0 <= W[1] <= y1: ax.text(W[0], W[1], t['text'], color=col, fontsize=8)
ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal'); ax.grid(True, lw=0.3)
ax.ticklabel_format(useOffset=False, style='plain')
fig.savefig(out, bbox_inches='tight')
