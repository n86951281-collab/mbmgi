"""解析 pdf_dump 解密後的頁面內容串流：路徑（紙面 pt 座標）＋文字（用 ToUnicode 解碼）。
用法：python pdf_parse.py <dump資料夾> [overlay_config.json]
- 頁面依 Pages 樹的 Kids 順序命名 p1、p2…；各頁的內容串流與字型 ToUnicode 由 summary.json 自動找。
- 自動找不到時，在設定檔 pdf.objects 指定，例：{"p1": {"contents": [15, 19, 30], "tounicode": 56}}。
輸出：parsed.json、texts.txt（頁、x、y、字高、角度、文字；用來分出段名、地號、比例尺標示）。"""
import re, json, sys, math, pathlib

D = pathlib.Path(sys.argv[1])
CFG = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8')) if len(sys.argv) > 2 else {}
SUM = json.loads((D / 'summary.json').read_text(encoding='utf-8'))


def load(n): return (D / f'obj{n}.bin').read_bytes()
def body(n): return SUM.get(str(n), '')
def refs(s): return [int(x) for x in re.findall(r'(\d+)\s+\d+\s+R', s)]


def cmap(n):
    s = load(n).decode('latin1'); m = {}
    for blk in re.findall(r'beginbfchar(.*?)endbfchar', s, re.S):
        for a, b in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            m[int(a, 16)] = chr(int(b, 16))
    for blk in re.findall(r'beginbfrange(.*?)endbfrange', s, re.S):
        for a, b, c in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            for i in range(int(a, 16), int(b, 16) + 1):
                m[i] = chr(int(c, 16) + i - int(a, 16))
    return m


# ---- 自動找頁面、內容串流、字型
def dict_entry(s, key):
    """取字典中 key 的值：間接參照回傳該物件內容，內嵌 << >> 回傳字串本身。"""
    m = re.search(r'/' + key + r'\s*(\d+)\s+\d+\s+R', s)
    if m: return body(int(m.group(1)))
    m = re.search(r'/' + key + r'\s*<<', s)
    if not m: return ''
    i, depth = m.end() - 2, 0
    for j in range(i, len(s) - 1):
        if s[j:j+2] == '<<': depth += 1
        elif s[j:j+2] == '>>':
            depth -= 1
            if depth == 0: return s[i:j+2]
    return s[i:]


def fonts_of(res):
    """回傳 {字型資源名: ToUnicode cmap}。"""
    out = {}
    fd = dict_entry(res, 'Font')
    for name, n in re.findall(r'/([^\s/<>\[\]]+)\s*(\d+)\s+\d+\s+R', fd):
        m = re.search(r'/ToUnicode\s*(\d+)\s+\d+\s+R', body(int(n)))
        if m: out[name.encode()] = cmap(int(m.group(1)))
    return out


def page_list():
    roots = [k for k, v in SUM.items() if re.search(r'/Type\s*/Pages\b', v) and '/Parent' not in v]
    pages = []
    def walk(n):
        v = body(n)
        if re.search(r'/Type\s*/Pages\b', v):
            for k in refs(re.search(r'/Kids\s*\[(.*?)\]', v, re.S).group(1)): walk(k)
        elif re.search(r'/Type\s*/Page\b', v): pages.append(n)
    for r in roots: walk(int(r))
    return pages


def page_objects(n):
    v = body(n)
    m = re.search(r'/Contents\s*(\d+)\s+\d+\s+R', v)
    if m:
        c = int(m.group(1)); cb = body(c)
        contents = refs(cb) if '[stream' not in cb and cb.strip().startswith('[') else [c]
    else:
        contents = refs(re.search(r'/Contents\s*\[(.*?)\]', v, re.S).group(1))
    res = dict_entry(v, 'Resources')
    forms = []
    for name, x in re.findall(r'/([^\s/<>\[\]]+)\s*(\d+)\s+\d+\s+R', dict_entry(res, 'XObject')):
        xb = body(int(x))
        if '/Subtype/Form' in xb.replace(' ', '') and fonts_of(dict_entry(xb, 'Resources')):
            forms.append(int(x))
    return contents, fonts_of(res), forms


def unesc(raw):
    out = bytearray(); i = 0
    while i < len(raw):
        c = raw[i]
        if c == 0x5c:
            n = raw[i+1]
            if n in b'01234567':
                j = i + 1; v = 0; k = 0
                while k < 3 and j < len(raw) and raw[j] in b'01234567':
                    v = v * 8 + raw[j] - 48; j += 1; k += 1
                out.append(v & 255); i = j; continue
            out.append({ord('n'): 10, ord('r'): 13, ord('t'): 9, ord('b'): 8, ord('f'): 12}.get(n, n)); i += 2; continue
        out.append(c); i += 1
    return bytes(out)


def decode(raw, m):
    b = unesc(raw)
    return ''.join(m.get(int.from_bytes(b[i:i+2], 'big'), '?') for i in range(0, len(b) - 1, 2))


TOK = re.compile(rb'\((?:\\.|[^\\)])*\)|\[|\]|/[^\s/\[\]()<>]+|-?\d*\.?\d+|[A-Za-z\'"*]+', re.S)


def mul(a, b):
    return [a[0]*b[0]+a[1]*b[2], a[0]*b[1]+a[1]*b[3], a[2]*b[0]+a[3]*b[2], a[2]*b[1]+a[3]*b[3],
            a[4]*b[0]+a[5]*b[2]+b[4], a[4]*b[1]+a[5]*b[3]+b[5]]


def run(streams, fonts):
    """fonts: {資源名(bytes): cmap}；Tf 切換字型時跟著換 cmap。"""
    m = next(iter(fonts.values())) if fonts else {}
    ctm = [1, 0, 0, 1, 0, 0]; stack = []; st = []
    paths = []; cur = []; sub = []; texts = []; tm = [1,0,0,1,0,0]; tlm = tm[:]; fs = 12; lw = 1; col = None; fill = None
    def P(x, y): return (ctm[0]*x+ctm[2]*y+ctm[4], ctm[1]*x+ctm[3]*y+ctm[5])
    for data in streams:
        for t in TOK.findall(data):
            if t[:1] == b'(':
                st.append(('s', t[1:-1])); continue
            if t[:1] == b'/' or t in (b'[', b']'):
                st.append(('n', t)); continue
            try:
                st.append(('f', float(t))); continue
            except ValueError: pass
            op = t.decode(); a = [v for k, v in st if k == 'f']
            if op == 'q': stack.append(ctm[:])
            elif op == 'Q': ctm = stack.pop() if stack else ctm
            elif op == 'cm': ctm = mul(a[-6:], ctm)
            elif op == 'w': lw = a[-1]
            elif op == 'RG': col = tuple(a[-3:])
            elif op == 'rg': fill = tuple(a[-3:])
            elif op == 'm':
                if len(sub) > 1: cur.append(sub)
                sub = [P(*a[-2:])]
            elif op == 'l': sub.append(P(*a[-2:]))
            elif op == 're':
                x, y, w, h = a[-4:]
                if len(sub) > 1: cur.append(sub)
                sub = [P(x, y), P(x+w, y), P(x+w, y+h), P(x, y+h), P(x, y)]
            elif op == 'h':
                if sub: sub.append(sub[0])
            elif op in ('S', 's', 'f', 'F', 'B', 'b', 'f*', 'B*', 'n'):
                if len(sub) > 1: cur.append(sub)
                if op != 'n':
                    for s_ in cur: paths.append({'op': op, 'lw': lw, 'col': col, 'fill': fill, 'pts': s_})
                cur = []; sub = []
            elif op == 'BT': tm = [1,0,0,1,0,0]; tlm = tm[:]
            elif op == 'Tf':
                fs = a[-1]
                names = [v for k, v in st if k == 'n']
                if names and names[-1][1:] in fonts: m = fonts[names[-1][1:]]
            elif op == 'Td': tlm = mul([1,0,0,1,a[-2],a[-1]], tlm); tm = tlm[:]
            elif op == 'TD': tlm = mul([1,0,0,1,a[-2],a[-1]], tlm); tm = tlm[:]
            elif op == 'Tm': tlm = a[-6:]; tm = tlm[:]
            elif op == 'Tj':
                s = [v for k, v in st if k == 's'][-1]
                full = mul(tm, ctm)
                texts.append({'x': full[4], 'y': full[5], 'size': fs * (full[0]**2+full[1]**2)**.5,
                              'rot': math.degrees(math.atan2(full[1], full[0])),
                              'text': decode(s, m)})
            st = []
    return paths, texts


override = CFG.get('pdf', {}).get('objects') or {}
res = {}
for i, pn in enumerate(page_list(), 1):
    page = f'p{i}'
    contents, fonts, forms = page_objects(pn)
    if page in override:
        contents = override[page]['contents']
        fonts = {b'F0': cmap(override[page]['tounicode'])}
    print(page, 'page obj', pn, 'contents', contents, 'fonts', [k.decode() for k in fonts], 'forms', forms)
    paths, texts = run([load(n) for n in contents], fonts)
    res[page] = {'paths': paths, 'texts': texts}
    print(page, len(paths), 'paths', len(texts), 'texts')
    for n in forms:                                   # 浮水印、頁首等表單 XObject 的文字（僅列出）
        _, tx = run([load(n)], fonts_of(dict_entry(body(n), 'Resources'))); print('  form', n, [t['text'] for t in tx])
(D / 'parsed.json').write_text(json.dumps(res, ensure_ascii=False), encoding='utf-8')
with open(D / 'texts.txt', 'w', encoding='utf-8') as f:
    for page in res:
        for t in res[page]['texts']:
            f.write(f"{page}\t{t['x']:.1f}\t{t['y']:.1f}\t{t['size']:.1f}\t{t['rot']:.0f}\t{t['text']}\n")
