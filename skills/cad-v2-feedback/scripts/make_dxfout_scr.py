"""產生 accoreconsole 用的 DXFOUT 指令檔（ASCII、CRLF）。

路徑必須是純英數的完整長路徑：含中文會在 accoreconsole 變成「?」而找不到檔，
含「~」（例如 ADMINI~1 短檔名）也會失敗，兩種都直接停止。

用法：
  python make_dxfout_scr.py <輸出.dxf> <指令檔.scr> [--version 2018] [--precision 16]

搭配（DWG 先複製到純英數暫存資料夾）：
  accoreconsole.exe /i <暫存>\\v2.dwg /s <暫存>\\dxfout.scr /l zh-TW
或直接用同資料夾的 run_dxfout.ps1（含複製、逾時結束程序、檢查輸出）。
"""
import argparse
import os
import sys

VERSIONS = {"2000", "2004", "2007", "2010", "2013", "2018"}


def chk(p, what):
    full = os.path.abspath(p)
    if not full.isascii():
        sys.exit(f"{what}路徑含非英數字元（accoreconsole 會變成「?」）：{full}\n"
                 "→ 先複製到純英數資料夾，例如 D:\\cadtmp\\v2.dwg")
    if "~" in full:
        sys.exit(f"{what}路徑含「~」短檔名（例如 ADMINI~1），accoreconsole 讀不到：{full}\n"
                 "→ PowerShell 用 [IO.Path]::GetFullPath(...) 或 (Get-Item ...).FullName 展開成長檔名")
    return full


def main():
    ap = argparse.ArgumentParser(description="產生 DXFOUT 指令檔")
    ap.add_argument("out_dxf", help="輸出 DXF（純英數完整路徑）")
    ap.add_argument("scr", help="指令檔輸出位置（純英數完整路徑）")
    ap.add_argument("--version", default="2018", choices=sorted(VERSIONS), help="DXF 版本，預設 2018")
    ap.add_argument("--precision", type=int, default=16, help="小數位數 0～16，預設 16")
    a = ap.parse_args()
    out = chk(a.out_dxf, "輸出 DXF ")
    scr = chk(a.scr, "指令檔 ")
    if not 0 <= a.precision <= 16:
        sys.exit("--precision 要在 0～16")
    # FILEDIA 0：指令列模式；_V 指定版本；最後 QUIT _Y 放棄對來源 DWG 的任何變更（來源只讀）
    body = (f"_.FILEDIA 0\n"
            f"_.DXFOUT \"{out}\" _V {a.version} {a.precision}\n"
            f"_.QUIT _Y\n")
    os.makedirs(os.path.dirname(scr), exist_ok=True)
    with open(scr, "w", encoding="ascii", newline="\r\n") as f:
        f.write(body)
    print(body, end="")
    print(f"→ {scr}")


if __name__ == "__main__":
    main()
