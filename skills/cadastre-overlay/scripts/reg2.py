"""定位參數：初值（標示比例尺＋單點）與控制點相似轉換（比例、旋轉、平移）。
用法：
  python reg2.py init <overlay_config.json> <輸出 reg_init.json>
      依 registration.init 建初值：比例用 pdf.scale_denominator，旋轉 0。
  python reg2.py fit  <overlay_config.json> <輸入 reg.json> <輸出 reg_fit.json> <輸出 殘差表.csv>
      依 registration.controls（observed → twd97）對每頁做最小二乘相似轉換，套到該頁定位參數，並輸出殘差表。
      控制點 pages 省略時套到所有頁；某頁少於 2 點時只做平移並警告（比例、旋轉無法驗證）。
說明：2 點時相似轉換剛好有解，殘差恆為 0，不能當檢核；要用 probe.py 在兩端量多條地籍線與網頁截圖比對，
     殘差表另加檢核線結果（P33：北端 ≤0.05 m、南端南北向線 ≤0.12 m、東西向路界 ≤0.2 m）。3 點以上殘差才有意義。
P33 實測：標示 1/3000 實際大 0.9%（×1.00915），旋轉 −0.128°；只用單點時南端偏北約 1.05 m、偏東約 0.26 m。"""
import sys, json, math, csv, pathlib
import numpy as np
from common import load_config, scale_m_per_pt


def helmert(src, dst):
    """最小二乘 2D 相似轉換 dst ≈ k R(φ) src + t；回傳 (k, φ rad, t)。"""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    cs, cd = src.mean(0), dst.mean(0)
    a, b = src - cs, dst - cd
    den = (a ** 2).sum()
    p = ((a[:, 0] * b[:, 0]) + (a[:, 1] * b[:, 1])).sum() / den      # k cosφ
    q = ((a[:, 0] * b[:, 1]) - (a[:, 1] * b[:, 0])).sum() / den      # k sinφ
    k, phi = math.hypot(p, q), math.atan2(q, p)
    t = cd - np.array([p * cs[0] - q * cs[1], q * cs[0] + p * cs[1]])
    return k, phi, t


def apply(k, phi, t, P):
    c, s = math.cos(phi), math.sin(phi); P = np.asarray(P, float)
    return k * np.c_[c * P[..., 0] - s * P[..., 1], s * P[..., 0] + c * P[..., 1]].reshape(P.shape) + t


mode = sys.argv[1]; CFG = load_config(sys.argv[2]); RC = CFG['registration']
if mode == 'init':
    S = scale_m_per_pt(CFG['pdf']['scale_denominator'])
    reg = {pg: {'pref': v['pref'], 'wref': v['wref'], 'theta_deg': 0.0, 'scale_m_per_pt': S,
                'source': RC.get('init_source', 'labelled scale + single point')} for pg, v in RC['init'].items()}
    pathlib.Path(sys.argv[3]).write_text(json.dumps(reg, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(reg, ensure_ascii=False))
elif mode == 'fit':
    reg = json.loads(pathlib.Path(sys.argv[3]).read_text(encoding='utf-8'))
    ctrl = RC['controls']; rows = []
    for pg, r in reg.items():
        cs = [c for c in ctrl if pg in c.get('pages', reg.keys())]
        if not cs: print(pg, '沒有控制點，未修正'); continue
        src = np.array([c['observed'] for c in cs]); dst = np.array([c['twd97'] for c in cs])
        if len(cs) == 1:
            print(f'警告 {pg}：只有 1 個控制點，只做平移，比例與旋轉無法驗證')
            k, phi, t = 1.0, 0.0, dst[0] - src[0]
        else:
            k, phi, t = helmert(src, dst)
        r['wref'] = apply(k, phi, t, np.array(r['wref'])).tolist()
        r['scale_m_per_pt'] *= k
        r['theta_deg'] += math.degrees(phi)
        r['source'] = 'controls: ' + '; '.join(f"{c['name']}({c['twd97'][0]},{c['twd97'][1]})" for c in cs)
        r['fit'] = {'n_controls': len(cs), 'scale_factor': k, 'scale_change_pct': (k - 1) * 100,
                    'rotation_deg': math.degrees(phi), 'implied_denominator': CFG['pdf']['scale_denominator'] * r['scale_m_per_pt'] / scale_m_per_pt(CFG['pdf']['scale_denominator'])}
        fitted = apply(k, phi, t, src)
        for c, f in zip(cs, fitted):
            dE, dN = float(f[0] - c['twd97'][0]) + 0.0, float(f[1] - c['twd97'][1]) + 0.0
            rows.append([pg, c['name'], *c['twd97'], *c['observed'], round(dE, 3), round(dN, 3), round(math.hypot(dE, dN), 3)])
        print(f"{pg}: 比例 ×{k:.5f}（{(k - 1) * 100:+.2f}%）旋轉 {math.degrees(phi):+.4f}°  控制點 {len(cs)}")
        if len(cs) == 2: print(f'  {pg}：2 點時殘差恆為 0，請用 probe.py 量兩端檢核線，補進殘差表')
    pathlib.Path(sys.argv[4]).write_text(json.dumps(reg, indent=1, ensure_ascii=False), encoding='utf-8')
    with open(sys.argv[5], 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['頁', '控制點', 'TWD97_E', 'TWD97_N', '套繪量得_E', '套繪量得_N', '殘差_E(m)', '殘差_N(m)', '殘差(m)'])
        w.writerows(rows)
    for row in rows: print(row)
else:
    sys.exit('mode 要用 init 或 fit')
