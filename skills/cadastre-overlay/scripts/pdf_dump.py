"""解密（Standard V1/R2，40-bit RC4，空白使用者密碼）並傾印 PDF 物件與串流。
用法：python pdf_dump.py <謄本.pdf> <dump資料夾>
輸出：obj<n>.bin（解密、解壓後的串流）、summary.json（各物件字典，供 pdf_parse 自動找頁面）。
沒加密的 PDF 直接傾印；加密版本不是 V1/R2 時停止並提示（要另外擴充 R3 以上的金鑰演算法）。"""
import hashlib, re, sys, zlib, json, pathlib

src = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
b = src.read_bytes()
PAD = bytes.fromhex('28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A')


def rc4(key, data):
    S = list(range(256)); j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) & 255; S[i], S[j] = S[j], S[i]
    i = j = 0; o = bytearray()
    for c in data:
        i = (i + 1) & 255; j = (j + S[i]) & 255; S[i], S[j] = S[j], S[i]
        o.append(c ^ S[(S[i] + S[j]) & 255])
    return bytes(o)


m_enc = re.search(rb'/Filter\s*/Standard(.*?)>>', b, re.S)
key = None; enc_obj = -1
if m_enc:
    enc = m_enc.group(1)
    V = int(re.search(rb'/V\s*(\d+)', enc).group(1))
    R = int(re.search(rb'/R\s*(\d+)', enc).group(1))
    print('encryption V', V, 'R', R)
    if (V, R) != (1, 2):
        sys.exit(f'只支援 Standard V1/R2（40-bit RC4），本檔為 V{V}/R{R}，需擴充金鑰演算法')
    O = bytes.fromhex(re.search(rb'/O\s*<([0-9A-Fa-f]+)>', enc).group(1).decode())
    P = int(re.search(rb'/P\s*(-?\d+)', enc).group(1))
    ID0 = bytes.fromhex(re.search(rb'/ID\s*\[\s*<([0-9A-Fa-f]+)>', b).group(1).decode())
    key = hashlib.md5(PAD + O + (P & 0xffffffff).to_bytes(4, 'little') + ID0).digest()[:5]
    m = re.search(rb'(\d+)\s+0\s+obj\s*<<\s*/Filter\s*/Standard', b)
    enc_obj = int(m.group(1)) if m else -1
else:
    print('no /Standard encryption')


def okey(n, g):
    return hashlib.md5(key + n.to_bytes(3, 'little') + g.to_bytes(2, 'little')).digest()[:10]


objs = {}
for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', b):
    n, g = int(m.group(1)), int(m.group(2))
    end = b.find(b'endobj', m.end())
    objs[n] = (g, m.end(), end)


def length_of(d):
    m = re.search(rb'/Length\s+(\d+)\s+(\d+)\s+R', d)
    if m:
        g, s, e = objs[int(m.group(1))]
        return int(re.search(rb'\d+', b[s:e]).group())
    return int(re.search(rb'/Length\s+(\d+)', d).group(1))


summary = {}
for n, (g, s, e) in sorted(objs.items()):
    body = b[s:e]
    k = body.find(b'stream')
    if k < 0:
        summary[n] = body[:4000].decode('latin1'); continue
    d = body[:k]
    st = s + k + 6
    if b[st:st+2] == b'\r\n': st += 2
    elif b[st:st+1] in (b'\n', b'\r'): st += 1
    L = length_of(d)
    data = b[st:st+L]
    if key is not None and n != enc_obj: data = rc4(okey(n, g), data)
    if b'/FlateDecode' in d:
        try: data = zlib.decompress(data)
        except Exception as ex: data = b'#ERR ' + str(ex).encode()
    (out / f'obj{n}.bin').write_bytes(data)
    summary[n] = d.decode('latin1')[:4000] + f' [stream {len(data)} bytes]'
(out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('objects', len(objs))
