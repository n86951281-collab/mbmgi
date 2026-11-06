"""併入後驗證：原測量圖每個「圖層＋圖元種類」的物件數必須和合併檔相同（原圖沒被動到），只多出地籍兩個新圖層。
用法：python verify_merged.py <原測量圖.dxf> <merged.dxf> <輸出 verify.txt> <overlay_config.json>
結果第一行 PASS／FAIL；FAIL 時結束碼 1。"""
import sys, json, pathlib, ezdxf
from collections import Counter
a = ezdxf.readfile(sys.argv[1]); b = ezdxf.readfile(sys.argv[2]); out = open(sys.argv[3], 'w', encoding='utf-8')
CFG = json.loads(pathlib.Path(sys.argv[4]).read_text(encoding='utf-8'))
NEW = list(CFG['output']['layers']); ST = CFG['output']['text_style']['name']
ca = Counter((e.dxf.layer, e.dxftype()) for e in a.modelspace())
cb = Counter((e.dxf.layer, e.dxftype()) for e in b.modelspace())
diff = {k: (ca.get(k, 0), cb.get(k, 0)) for k in set(ca) | set(cb) if ca.get(k, 0) != cb.get(k, 0)}
changed_orig = {k: v for k, v in diff.items() if k[0] not in NEW}
added = {k: v[1] for k, v in diff.items() if k[0] in NEW}
la = {l.dxf.name for l in a.layers}; lb = {l.dxf.name for l in b.layers}
lost_layers = sorted(la - lb)
ok = not changed_orig and not lost_layers and all(n in lb for n in NEW)
print('PASS' if ok else 'FAIL', file=out)
print('original layer/type counts changed (orig, merged):', changed_orig, file=out)
print('original layers missing in merged:', lost_layers, file=out)
print('added on new layers:', added, file=out)
print('new layers:', [(l.dxf.name, l.dxf.color, l.dxf.linetype) for l in b.layers if l.dxf.name in NEW], file=out)
if ST in b.styles:
    st = b.styles.get(ST); print('style:', ST, st.dxf.font, st.dxf.get('bigfont'), st.dxf.width, file=out)
else:
    print('style missing:', ST, file=out)
sample = set(CFG.get('verify', {}).get('sample_texts', []))
for e in b.modelspace().query('TEXT'):
    if e.dxf.layer in NEW and e.dxf.text in sample:
        print('TEXT', e.dxf.text, round(e.dxf.insert.x, 2), round(e.dxf.insert.y, 2), e.dxf.height, e.dxf.style, file=out)
blocks = [e for e in b.modelspace().query('INSERT') if 'cadastre' in e.dxf.name.lower()]
print('leftover cadastre block refs (should be 0, use -INSERT "*path"):', len(blocks), file=out)
out.close()
print('PASS' if ok else 'FAIL', 'added', added)
sys.exit(0 if ok and not blocks else 1)
