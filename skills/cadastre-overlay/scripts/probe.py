"""量地籍線位置：在控制點附近拉一條東西向探測線（N=yp）與兩條南北向探測線（E=xw、xe），列出地籍線交點座標。
用途：與網頁截圖（標記點到各條地籍線的距離，用截圖比例尺 px/m 量）比對，得到控制點的 observed 座標與檢核線殘差。
用法：python probe.py <cadastre.dxf 或 merged.dxf> <yp> <xw> <xe> [半寬 m，預設 15] [圖層，預設 地籍線]
P33 範例：python probe.py cadastre.dxf 2678767.941 229262 229276"""
import sys, ezdxf, numpy as np
d = ezdxf.readfile(sys.argv[1]); yp, xw, xe = map(float, sys.argv[2:5])
half = float(sys.argv[5]) if len(sys.argv) > 5 else 15.0
layer = sys.argv[6] if len(sys.argv) > 6 else '地籍線'
segs = []
for e in d.modelspace().query('LWPOLYLINE'):
    if e.dxf.layer != layer: continue
    p = np.array([tuple(v[:2]) for v in e.get_points('xy')])
    if e.closed: p = np.vstack([p, p[:1]])
    segs += [(a, b) for a, b in zip(p, p[1:])]
xc = (xw + xe) / 2
def cross_h(y):
    out = []
    for (x0, y0), (x1, y1) in segs:
        if (y0 - y) * (y1 - y) < 0: out.append(x0 + (x1 - x0) * (y - y0) / (y1 - y0))
    return sorted(float(round(v, 2)) for v in set(np.round(out, 2)) if xc - half < v < xc + half)
def cross_v(x):
    out = []
    for (x0, y0), (x1, y1) in segs:
        if (x0 - x) * (x1 - x) < 0: out.append(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
    return sorted(float(round(v, 2)) for v in set(np.round(out, 2)) if yp - half < v < yp + half)
print('E of N-S lines at N', yp, cross_h(yp))
print('N of E-W lines at E', xw, cross_v(xw))
print('N of E-W lines at E', xe, cross_v(xe))
