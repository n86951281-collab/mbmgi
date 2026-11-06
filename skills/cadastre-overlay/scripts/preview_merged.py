"""合併檔預覽＋自動檢查：地號壓地籍線、文字互疊、引線壓字三項都要 0。
用法：python preview_merged.py <merged.dxf> <輸出.png> <輸出.pdf> <輸出 overlap.txt> <overlay_config.json>
PNG：第一個預覽範圍（全區，A3 橫式比例）；PDF：每個預覽範圍一頁。報告第一行是標註數與問題數。
字寬用 GENISO 估算 0.9h × 寬度係數；這是程式預覽，交付前仍要在 CAD 開檔或 PUBLISH 目視。"""
import sys, json, pathlib, ezdxf, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from common import survey_lines
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
doc = ezdxf.readfile(sys.argv[1]); msp = doc.modelspace(); png_n, pdf, rep = sys.argv[2:5]
CFG = json.loads(pathlib.Path(sys.argv[5]).read_text(encoding='utf-8'))
LAYER_LINE, LAYER_LOT = list(CFG['output']['layers'])[:2]
PV = CFG['preview']; TITLE = PV.get('title', '測量圖套繪地籍（TWD97）'); TXT_H = CFG['output']['text_height_m']
lines = {'s': [], 'c': []}
for L, p in survey_lines(msp, set(CFG['survey'].get('skip_layers', []))):
    lines['c' if L == LAYER_LINE else 's'].append(np.array(p))
texts = [e for e in msp.query('TEXT') if e.dxf.layer == LAYER_LOT]
# overlap check: text box (width ≈ 0.9*h*wf per char for GENISO) vs 地籍線 segments
segs = np.vstack([np.c_[p[:-1], p[1:]] for p in lines['c'] if len(p) > 1])
def seg_box_hit(x0, y0, x1, y1):
    a, b = segs[:, :2], segs[:, 2:]
    t = np.linspace(0, 1, 9)[:, None, None]
    P = a + (b - a) * t
    return np.any((P[..., 0] > x0) & (P[..., 0] < x1) & (P[..., 1] > y0) & (P[..., 1] < y1))
bad = []; boxes = []
for e in texts:
    h = e.dxf.height; w = len(e.dxf.text) * h * 0.9 * e.dxf.width
    x, y = e.dxf.insert.x, e.dxf.insert.y
    if e.dxf.get('rotation', 0) == 90: bx = (x - h, y, x, y + w)
    else: bx = (x, y, x + w, y + h)
    boxes.append((e.dxf.text, bx))
    if seg_box_hit(*bx): bad.append(('壓線', e.dxf.text, round(x, 1), round(y, 1)))
for i in range(len(boxes)):
    for j in range(i + 1, len(boxes)):
        a, b = boxes[i][1], boxes[j][1]
        if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]: bad.append(('文字互疊', boxes[i][0], boxes[j][0]))
leaders = [e for e in msp.query('LINE') if e.dxf.layer == LAYER_LOT]
for L in leaders:
    p, q = np.array(L.dxf.start)[:2], np.array(L.dxf.end)[:2]
    P = p + (q - p) * np.linspace(0.05, 0.95, 20)[:, None]
    for name, bx in boxes:
        if np.any((P[:, 0] > bx[0]) & (P[:, 0] < bx[2]) & (P[:, 1] > bx[1]) & (P[:, 1] < bx[3])): bad.append(('引線壓字', name))
with open(rep, 'w', encoding='utf-8') as f:
    f.write(f'labels {len(texts)}; problems: {len(bad)}\n')
    for b in bad: f.write(f'{b}\n')
def draw(ax, x0, x1, y0, y1, fs):
    for p in lines['s']: ax.plot(p[:, 0], p[:, 1], color='0.55', lw=0.5)
    for p in lines['c']: ax.plot(p[:, 0], p[:, 1], color='#B000B0', lw=0.6)
    for e in texts:
        x, y = e.dxf.insert.x, e.dxf.insert.y
        if x0 <= x <= x1 and y0 <= y <= y1:
            ax.text(x, y, e.dxf.text, color='#B000B0', fontsize=fs * e.dxf.height / TXT_H, rotation=e.dxf.get('rotation', 0),
                    rotation_mode='anchor', ha='left', va='bottom')
    for L in leaders: ax.plot([L.dxf.start.x, L.dxf.end.x], [L.dxf.start.y, L.dxf.end.y], color='#B000B0', lw=0.5)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal'); ax.ticklabel_format(useOffset=False, style='plain')
    ax.tick_params(labelsize=8); ax.grid(True, lw=0.2)
W = PV['windows']
fig, ax = plt.subplots(figsize=(16.54, 11.69), dpi=150)
draw(ax, *W[0][:4], 7)
ax.set_title(f'{TITLE}｜紫：地籍線、地號｜灰：測量圖', fontsize=12)
fig.savefig(png_n, bbox_inches='tight'); plt.close(fig)
with PdfPages(pdf) as pp:
    for i, (x0, x1, y0, y1, ttl) in enumerate(W):
        fig, ax = plt.subplots(figsize=(16.54, 11.69)); draw(ax, x0, x1, y0, y1, 7 if i == 0 else 12)
        ax.set_title(f'{TITLE}— {ttl}', fontsize=14); pp.savefig(fig, bbox_inches='tight'); plt.close(fig)
print(len(texts), len(bad))
