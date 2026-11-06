"""地籍套繪共用函式：讀設定檔、PDF 頁面座標 → TWD97 轉換、讀測量圖線段。"""
import json, math, pathlib
import numpy as np


def load_config(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))


def load_reg(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))


def scale_m_per_pt(denominator):
    """謄本標示比例尺 1/denominator 時，PDF 1 pt 對應的地面公尺數。"""
    return 25.4 / 72 / 1000 * denominator


def xf(P, r):
    """world = R(theta) * s * (p - pref) + wref；r 為定位參數 json 中一頁的設定。"""
    th = math.radians(r['theta_deg']); c, s = math.cos(th), math.sin(th)
    q = (np.asarray(P, float) - r['pref']) * r['scale_m_per_pt']
    return np.c_[c * q[:, 0] - s * q[:, 1], s * q[:, 0] + c * q[:, 1]] + r['wref']


def survey_lines(msp, skip=(), skip_prefixes=(), close_lw=True):
    """回傳 [(圖層, [(x, y), ...]), ...]：LINE、LWPOLYLINE、POLYLINE；略過指定圖層。
    close_lw=False 時封閉 LWPOLYLINE 不補回起點（P33 的 register、overlay 是這樣算的）。"""
    out = []
    for e in msp:
        L = e.dxf.layer
        if L in skip or any(L.startswith(p) for p in skip_prefixes): continue
        t = e.dxftype()
        if t == 'POLYLINE': p = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        elif t == 'LWPOLYLINE':
            p = [tuple(q[:2]) for q in e.get_points('xy')]
            if close_lw and e.closed and p: p.append(p[0])
        elif t == 'LINE': p = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        else: continue
        if p: out.append((L, p))
    return out
