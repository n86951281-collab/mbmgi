"""（選用，除錯用）放大 PDF 某頁的一小塊（紙面 pt），標出頂點與地號，用來找控制點附近的地籍角點 pt 座標。
用法：python pdf_zoom.py <dump資料夾> <頁 p1> <x0> <x1> <y0> <y1> <輸出.png> [--vertices]
--vertices：另把範圍內地籍線頂點座標（pt，小數 2 位）與附近地號位置印到螢幕（P33 的 near.py 併入此處）。"""
import json, sys, pathlib
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
args = [a for a in sys.argv[1:] if a != '--vertices']; show_v = '--vertices' in sys.argv
D = pathlib.Path(args[0]); res = json.loads((D / 'parsed.json').read_text(encoding='utf-8'))
page = args[1]; x0, x1, y0, y1 = map(float, args[2:6]); out = args[6]
fig, ax = plt.subplots(figsize=(10, 10 * (y1 - y0) / (x1 - x0)), dpi=110)
for p in res[page]['paths']:
    if p['op'] != 'S': continue
    xs, ys = zip(*p['pts']); ax.plot(xs, ys, 'k-', lw=0.8, marker='.', ms=3)
for t in res[page]['texts']:
    if x0 <= t['x'] <= x1 and y0 <= t['y'] <= y1: ax.text(t['x'], t['y'], t['text'], color='r', fontsize=9)
ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal')
ax.set_xticks([x0 + i for i in range(int(x1 - x0) + 1)], minor=True); ax.set_yticks([y0 + i for i in range(int(y1 - y0) + 1)], minor=True)
ax.grid(True, which='both', lw=0.2)
fig.savefig(out, bbox_inches='tight')
if show_v:
    seen = set()
    for p in res[page]['paths']:
        if p['op'] != 'S': continue
        for q in p['pts']:
            if x0 <= q[0] <= x1 and y0 <= q[1] <= y1: seen.add((round(q[0], 2), round(q[1], 2)))
    print(sorted(seen))
    for t in res[page]['texts']:
        if x0 - 10 <= t['x'] <= x1 + 10 and y0 - 10 <= t['y'] <= y1 + 10: print(t['text'], round(t['x'], 1), round(t['y'], 1))
