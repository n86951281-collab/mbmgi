"""把 parsed.json 各頁畫成 PNG（紙面 pt 座標，含格線），看地籍線、地號、圖框位置，並統計線條樣式（找地籍線的顏色、線寬）。
用法：python pdf_preview.py <dump資料夾> [overlay_config.json]
有設定檔時，畫面範圍用 pdf.map_clip_pt；字高小於 pdf.label_max_size_pt 的文字（地號）用紅字標出。"""
import json, sys, pathlib
from collections import Counter
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
D = pathlib.Path(sys.argv[1]); res = json.loads((D / 'parsed.json').read_text(encoding='utf-8'))
CFG = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8')).get('pdf', {}) if len(sys.argv) > 2 else {}
clip = CFG.get('map_clip_pt', [36, 56, 559, 683])
LBL = CFG.get('label_max_size_pt', 6)
for page, r in res.items():
    fig, ax = plt.subplots(figsize=(16, 22), dpi=110)
    for p in r['paths']:
        xs, ys = zip(*p['pts'])
        if p['op'] in ('f', 'F', 'f*'):
            ax.fill(xs, ys, color=p['fill'] or (0.8, 0.8, 0.8), lw=0, alpha=0.5)
        else:
            ax.plot(xs, ys, color=p['col'] or (0, 0, 0), lw=max(0.3, p['lw']))
    for t in r['texts']:
        if t['size'] < LBL:
            ax.text(t['x'], t['y'], t['text'], fontsize=6, color='red')
    ax.set_aspect('equal'); ax.set_xlim(clip[0] - 6, clip[2] + 6); ax.set_ylim(clip[1] - 6, clip[3] + 6); ax.grid(True, lw=0.2)
    fig.savefig(D / f'preview_{page}.png', bbox_inches='tight'); plt.close(fig)
    print(page, Counter((p['op'], p['lw'], tuple(p['col'] or ()), tuple(p['fill'] or ())) for p in r['paths']).most_common(12))
