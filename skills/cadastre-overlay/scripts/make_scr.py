"""產生 accoreconsole 指令檔（ASCII）。路徑必須是純英數的完整長路徑，含中文或 ADMINI~1 短檔名時直接停止。
用法：
  python make_scr.py dxfout <輸出.dxf> <指令檔.scr>
      搭配：accoreconsole.exe /i <survey.dwg> /s <指令檔.scr> /l zh-TW   → 測量圖轉 DXF（2018 版、精度 16）
  python make_scr.py merge <cadastre.dxf> <輸出 merged.dwg> <輸出 merged.dxf> <指令檔.scr>
      搭配：accoreconsole.exe /i <survey.dwg> /s <指令檔.scr> /l zh-TW   → 以 *（分解）插入 cadastre.dxf 於 0,0、比例 1、旋轉 0，
      另存新 DWG（2018）與 DXF；原 survey.dwg 不存檔（QUIT _Y 放棄對原檔的變更）。"""
import sys, os


def chk(p):
    p = os.path.abspath(p)
    if not p.isascii() or '~' in p:
        sys.exit(f'路徑要純英數、不能用短檔名：{p}（先複製到純英數資料夾，PowerShell 用 [IO.Path]::GetFullPath 展開）')
    return p


mode = sys.argv[1]
if mode == 'dxfout':
    out, scr = chk(sys.argv[2]), sys.argv[3]
    body = f'_.FILEDIA 0\n_.DXFOUT "{out}" _V 2018 16\n_.QUIT _Y\n'
elif mode == 'merge':
    cad, dwg, dxf, scr = chk(sys.argv[2]), chk(sys.argv[3]), chk(sys.argv[4]), sys.argv[5]
    body = (f'_.FILEDIA 0\n_.-INSERT "*{cad}" 0,0 1 0\n_.ZOOM _E\n'
            f'_.SAVEAS 2018 "{dwg}"\n_.DXFOUT "{dxf}" _V 2018 16\n_.QUIT _Y\n')
else:
    sys.exit('mode 要用 dxfout 或 merge')
chk(scr)
with open(scr, 'w', encoding='ascii', newline='\r\n') as f:
    f.write(body)
print(body)
