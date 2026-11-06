"""（選用，除錯用）把測量圖某一段（N 範圍）依圖層上色畫出，找可當控制的道路邊線、側溝、房屋。
用法：python survey_plot.py <測量圖.dxf> <輸出.png> <N下限> <N上限> [overlay_config.json]
略過的圖層取設定檔 survey.skip_layers。"""
import sys, ezdxf, json, pathlib
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import survey_lines
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
doc = ezdxf.readfile(sys.argv[1]); msp = doc.modelspace()
out = pathlib.Path(sys.argv[2])
ylo, yhi = float(sys.argv[3]), float(sys.argv[4])
CFG = json.loads(pathlib.Path(sys.argv[5]).read_text(encoding='utf-8')) if len(sys.argv) > 5 else {}
skip = set(CFG.get('survey', {}).get('skip_layers', []))
cols = {}
cyc = plt.rcParams['axes.prop_cycle'].by_key()['color'] + ['black', 'magenta', 'olive', 'navy']
fig, ax = plt.subplots(figsize=(12, 16), dpi=110)
for L, p in survey_lines(msp, skip, close_lw=False):
    c = cols.setdefault(L, cyc[len(cols) % len(cyc)])
    xs, ys = zip(*p)
    ax.plot(xs, ys, color=c, lw=0.8, label=L if L not in ax.get_legend_handles_labels()[1] else None)
ax.legend(fontsize=7, loc='upper left'); ax.set_aspect('equal'); ax.set_ylim(ylo, yhi); ax.grid(True, lw=0.3)
ax.ticklabel_format(useOffset=False, style='plain')
fig.savefig(out, bbox_inches='tight')
