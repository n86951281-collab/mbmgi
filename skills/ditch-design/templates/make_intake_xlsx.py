# -*- coding: utf-8 -*-
"""產生「排水設計 案件條件表」xlsx 範本。

用法：python make_intake_xlsx.py <輸出.xlsx>
表上每一欄都有「設定鍵」，`intake_to_config.py` 依此轉成 ditch_config.json；
東山街（P33）範例值附在每列，方便對照填寫。
"""
import sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

FONT = "微軟正黑體"
BLUE = "3E5C76"; DARK = "1F2D3A"; LIGHT = "D8DFE6"; FILL_IN = "FFF8E1"
thin = Side(style="thin", color=DARK)
BD = Border(left=thin, right=thin, top=thin, bottom=thin)
HEAD_FILL = PatternFill("solid", fgColor=BLUE)
SEC_FILL = PatternFill("solid", fgColor=LIGHT)
IN_FILL = PatternFill("solid", fgColor=FILL_IN)
WRAP = Alignment(wrap_text=True, vertical="center")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")

# (分類, 欄位, 說明, 東山街範例, 設定鍵, 必填, 沒填時)
REQ, OPT = "必填", "選填"
ROWS = [
    ("一、基本資料", None),
    ("基本", "案名（短）", "檔名用，英數或簡短中文", "P33_新社東山街側溝", "case_name", REQ, "無法開始"),
    ("基本", "工程名稱", "圖標欄、封面、預算書", "臺中市新社區東山街與協興街路口排水改善工程", "title_block.project", REQ, "無法開始"),
    ("基本", "主辦機關", "圖標欄、封面", "臺中市政府水利局", "title_block.agency", REQ, "無法開始"),
    ("基本", "主辦機關英文", "圖標欄", "Taichung Water Resources Bureau", "title_block.agency_en", OPT, "圖標欄英文留空"),
    ("基本", "設計單位", "封面、圖標欄", "辰璟工程技術顧問有限公司", "title_block.designer", REQ, "用公司名"),
    ("基本", "計畫名稱", "預算書封面", "【待補】", "budget.plan_name", OPT, "標【待補】"),
    ("基本", "工程編號", "預算書表頭", "【待補】", "budget.project_no", OPT, "標【待補】"),
    ("基本", "會計科目", "預算書表頭", "【待補】", "budget.account", OPT, "標【待補】"),
    ("基本", "施工地點", "預算書、一般說明", "臺中市新社區東山街與協興街路口", "budget.site", REQ, "停下來問"),
    ("基本", "出圖年月（民國）", "封面、預算書編製日期", "115年11月", "title_block.date_roc", OPT, "用當月"),

    ("二、輸入檔案", None),
    ("檔案", "測量圖", "DWG 或 DXF；含高程點或等高線（有 Z 值）", "src/survey_v2.dwg", "src_dxf", REQ, "無法開始"),
    ("檔案", "高程點圖層／圖塊", "高程點所在圖層", "圖層 0 的 INSERT（Z>0）", "layers.spot_insert_layer", REQ, "列出圖層請你指認"),
    ("檔案", "等高線圖層（首曲線／計曲線）", "沒有就留空", "（無，只有高程點）", "layers.contour_minor / contour_major", OPT, "只用高程點建地形"),
    ("檔案", "道路邊線、房屋、既有側溝圖層", "平面、橫斷面要畫的地物", "$00270(既有側溝)、SF、道路標線…", "layers.features", REQ, "列出圖層請你指認"),
    ("檔案", "整地圖（SG）", "有整地才給；四角或分區高程", "src/sg_pad.dwg（四角 476.99／477.00／477.88／477.80）", "sg.pad_dxf / sg.corner_z", OPT, "★停點問 EG 或 SG"),
    ("檔案", "地籍謄本 PDF", "地籍套繪圖用", "地籍圖謄本.pdf", "cadastre.pdf", OPT, "不出 L-01"),
    ("檔案", "地籍控制點（≥2 點 TWD97）", "相似轉換用，回報殘差", "≥2 點（P33 實際點位見 cadastral_sheet.py）", "cadastre.control_points", OPT, "不出 L-01"),
    ("檔案", "預算範本（同機關同年度 PCCES xls）", "版面與單價依據", "象鼻段 (預算書)…_1150915v1.xls", "budget.template_xls", REQ, "單價標【假設】"),
    ("檔案", "數量計算表範本", "版面依據", "象鼻段 數量計算表_1150922v1.xlsx", "qty.template_xlsx", OPT, "用一般 Excel 規則"),
    ("檔案", "引用標準圖 CAD", "他機關標準圖 DXF", "B20、A18（臺北市工務局）", "standards.import[]", OPT, "停下來問"),
    ("檔案", "設計條件手稿", "照片或 PDF 皆可", "設計條件手稿_v1.pdf", "design.sketch", OPT, "照本表"),

    ("三、定線與地面", None),
    ("定線", "道路中心線", "給 DXF 圖層，或兩端點 TWD97 座標（E,N）", "E229269.988 N2678883.406 → E229268.603 N2678767.941", "alignment.centerline", REQ, "★停點：用道路邊線中點試定線請你確認"),
    ("定線", "0K+000 位置", "下游端；中心線哪一端", "北端（下游）", "alignment.downstream", REQ, "預設下游端，停下來問"),
    ("定線", "側溝定線（各側）", "道路邊線圖層，或離中心線距離", "左側道路邊線A、右側道路邊線B", "alignment.bank_left_layer / bank_right_layer", REQ, "停下來問"),
    ("定線", "斷面間距 (m)", "橫斷面每幾公尺一刀", "20", "alignment.spacing", OPT, "20"),
    ("地面", "設計地面", "EG＝原地形；SG＝整地後", "SG", "design.ground", REQ, "★停點（必問）"),
    ("地面", "縱、橫斷面畫原地形線", "SG 時是否另畫 EG 對照", "否", "sg.draw_eg_line", OPT, "否"),
    ("地面", "路面點篩選高差 (m)", "剔除擋牆頂、溝底點", "0.25", "design.road_tol", OPT, "0.25"),

    ("四、構造物（明細填「側溝與集水井」工作表）", None),
    ("構造", "側溝型式", "箱涵式側溝／U 型溝／矩形明溝", "箱涵式側溝（甲乙種預鑄溝蓋板）", "design.ditch_type", REQ, "停下來問"),
    ("構造", "頂高決定方式", "貼齊地面（逐點）／指定縱坡／指定底高", "蓋板頂貼 SG，每 1 m 逐點", "design.top_rule", REQ, "停下來問"),
    ("構造", "蓋板厚 (m)", "", "0.23", "design.t_cover", REQ, "依標準圖"),
    ("構造", "溝壁厚 (m)", "", "0.20", "design.t_wall", REQ, "依標準圖"),
    ("構造", "底版厚 (m)", "", "0.20", "design.t_slab", REQ, "依標準圖"),
    ("構造", "墊層厚 (m)", "140 kgf/cm²", "0.10", "design.t_bed", REQ, "依標準圖"),
    ("構造", "集水井沉砂深 (m)", "管底高於井底", "0.30", "design.sump", OPT, "0.30"),
    ("構造", "集水井壁厚 (m)", "", "0.20", "design.well_wall", REQ, "依標準圖"),
    ("構造", "出口銜接", "接哪裡、銜接高程", "下游 0K+000 集水井 #AC1、#BC1（詳平面及縱斷面圖 v1.6）", "design.outlet", REQ, "停下來問"),
    ("構造", "混凝土強度 (kgf/cm²)", "結構／墊層", "溝體 210、蓋板與緣石 280、墊層 140", "design.fc", REQ, "停下來問"),
    ("構造", "鋼筋等級", "依號數", "D16、D19 用 SD420W；D10、D13 用 SD280W", "design.rebar_grade", REQ, "停下來問"),

    ("五、標準圖與施工", None),
    ("標準圖", "溝體標準圖", "引用（寫圖號）或自繪", "依 B20 改淨寬 110、淨高 100（超出 B20 適用範圍，另做配筋檢核）", "standards.ditch", REQ, "★停點"),
    ("標準圖", "護欄標準圖", "", "A18 鋼管護欄（臨時）", "standards.guardrail", OPT, "不出"),
    ("標準圖", "超出適用範圍時配筋檢核", "是／否", "是（配筋檢核表 W110 v1.2）", "standards.rc_check", REQ, "是"),
    ("施工", "臨時擋土型式", "鋼軌樁／鋼板樁／斜坡開挖", "鋼軌樁 L=3 m @1.0 m，路外側鐵板兼外模", "temp_shoring.type / pile_l / pile_sp", REQ, "★停點"),
    ("施工", "路外側樁心距外壁 (m)", "", "0.10", "temp_shoring.offset_out", OPT, "0.10"),
    ("施工", "路內側施工空間 (m)", "", "0.30", "temp_shoring.offset_in", OPT, "0.30"),
    ("施工", "既有構造物拆除", "逐項列；拆或不拆", "既有側溝全段打除", "demolish[]", REQ, "逐項問"),
    ("施工", "交通維持", "分階段、護欄設置側", "A、B 兩階段，臨時鋼管護欄設路內側＋兩端", "traffic.phases / guardrail_side", REQ, "停下來問"),

    ("六、預算與工期", None),
    ("預算", "單價來源優先順序", "同機關同年度 > 範例 > 他市×指數", "象鼻段 115 年 > 大湖範例 > 臺北市 112 年×K", "budget.price_sources[]", REQ, "照全域規則順序，標【假設】"),
    ("預算", "利潤管理保險費率", "", "8%×(壹.一+壹.二)", "budget.rates.profit", REQ, "停下來問"),
    ("預算", "品管費率", "", "2%（分段級距【待確認】）", "budget.rates.qc", REQ, "停下來問"),
    ("預算", "工程管理費", "", "依級距【待確認】", "budget.rates.mgmt", REQ, "停下來問"),
    ("預算", "空氣汙染防制費率", "", "0.35%", "budget.rates.air", REQ, "0.35%"),
    ("預算", "委外設計／監造費", "金額或費率", "312,182／312,181", "budget.design_fee / supervision_fee", OPT, "標【待補】"),
    ("工期", "工期（日曆天）", "直接指定；留空就用下兩列推算", "90", "schedule.days", OPT, "用每日施工量推算"),
    ("工期", "每日施工量", "側溝 m/日、集水井 日/座、拆除 m/日…", "（P33 未給，工期直接指定）", "schedule.rates", OPT, "標【假設】請你確認"),
    ("工期", "不計工作天", "雨天、假日折減", "日曆天，不另折減", "schedule.calendar", OPT, "日曆天"),

    ("七、出圖", None),
    ("出圖", "圖筆", "黑白／全彩", "全彩（有 Google 底圖）", "plot.ctb", OPT, "黑白"),
    ("出圖", "平面圖比例", "", "1/500", "plot.plan_scale", OPT, "1/500"),
    ("出圖", "縱斷面比例 H／V", "", "1/500／1/50", "plot.profile_scale", OPT, "1/500／1/50"),
    ("出圖", "橫斷面比例", "", "1/100", "plot.xs_scale", OPT, "1/100"),
    ("出圖", "檔名前綴", "依電腦", "(臺中48)", "file_prefix", OPT, "依電腦名"),
]

# 側溝與集水井明細：(編號, 側別, 種類, 起點樁號, 終點樁號, 內寬W, 內高H, 井內徑, 備註)
ITEMS_HEAD = ["編號", "側別", "種類", "起點樁號 (m)", "終點樁號 (m)", "內寬 W (m)", "內高 H (m)", "集水井內徑 (m)", "備註", "設定鍵"]
ITEMS_EX = [
    ("#A", "A（左）", "側溝", "0", "111.53", "1.10", "1.00", "", "東山街範例", "design.ditches[]"),
    ("#B", "B（右）", "側溝", "0", "110.48", "1.10", "1.00", "", "東山街範例", "design.ditches[]"),
    ("#AC1", "A（左）", "集水井", "0", "", "", "", "1.50", "東山街範例；內徑 150×150", "design.wells[]"),
    ("#BC1", "B（右）", "集水井", "0", "", "", "", "1.50", "東山街範例", "design.wells[]"),
]

STOPS = [
    ("1", "建地形", "8 視角預覽、高程點抽驗 RMSE", "section-drawings 步驟 2"),
    ("2", "定線", "全長、樁號範圍、0K+000 位置", "section-drawings 步驟 3"),
    ("3", "EG 或 SG", "SG 時四角高程逐角確認", "section-drawings 3-0、3-1"),
    ("4", "標準圖與擋土型式", "引用哪一型、是否超出適用範圍", "drawing-set、rc-section-check"),
    ("5", "既有構造物拆除", "逐項拆或不拆", "全域規則流程 5"),
    ("6", "單價與費率", "【假設】項目清單", "qty-budget"),
    ("7", "工期", "推算依據（每日施工量）", "ditch-design"),
]


def fit_height(ws, row, ncol, pt=14, min_h=30):
    """依字數估行數設列高（固定列高，不用自動）：14 pt 全形字約 2.6 欄寬單位、半形約 1.4；每行約 21 pt。"""
    import math
    lines = 1
    for c in range(1, ncol + 1):
        v = ws.cell(row=row, column=c).value
        if v is None: continue
        w = ws.column_dimensions[get_column_letter(c)].width or 8.43
        units = sum(2.6 if ord(ch) > 0x2E80 else 1.4 for ch in str(v)) * pt / 14
        lines = max(lines, math.ceil(units / max(w - 4, 1)))   # 留 4 單位給斷行不整齊（中英混排實測）
    ws.row_dimensions[row].height = max(min_h, lines * 21 + 8)


def head(ws, row, values, widths=None):
    for c, v in enumerate(values, 1):
        x = ws.cell(row=row, column=c, value=v)
        x.font = Font(name=FONT, size=14, bold=True, color="FFFFFF"); x.fill = HEAD_FILL; x.alignment = CENTER; x.border = BD
    ws.row_dimensions[row].height = 30
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def title(ws, text, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    x = ws.cell(row=1, column=1, value=text)
    x.font = Font(name=FONT, size=25, bold=True, color=DARK); x.alignment = CENTER
    ws.row_dimensions[1].height = 45


def page(ws, last_col, freeze="C3"):
    # 凍結只設一次：同一頁先 C3 再 A3，openpyxl 會留下 bottomRight 窗格選取，Excel COM 開檔失敗
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "2:2"
    ws.oddHeader.center.text = "排水設計 案件條件表"
    ws.oddFooter.center.text = "辰璟工程技術顧問有限公司　第 &P 頁／共 &N 頁"
    ws.freeze_panes = freeze


def main(out):
    wb = Workbook()
    # --- 填寫說明 ---
    ws = wb.active; ws.title = "填寫說明"
    title(ws, "排水設計 案件條件表｜填寫說明", 2)
    notes = [
        ("用途", "填完交給 Claude，依 SKILL ditch-design 自動出：平面、縱橫斷面、標準圖、地籍套繪、數量計算書、數量計算表、預算書、工期。"),
        ("怎麼填", "只填黃底「填寫值」欄。東山街範例欄是 P33 定案值，可照抄再改。留空時依「沒填時」欄處理。"),
        ("必填", "必填欄沒填，Claude 會停下來問，不會自己假設。"),
        ("★停點", "見「停點確認」工作表；每到一個停點，Claude 回報結果，等你確認才往下做。"),
        ("側溝與集水井", "每條側溝、每座集水井各一列，編號照全域規則（側別＋C＋序號，由下游起）。"),
        ("轉檔", "Claude 會用 intake_to_config.py 把本表轉成 ditch_config.json，回報缺漏項。"),
    ]
    for i, (k, v) in enumerate(notes, 3):
        a = ws.cell(row=i, column=1, value=k); b = ws.cell(row=i, column=2, value=v)
        for x in (a, b): x.font = Font(name=FONT, size=14, color=DARK); x.alignment = WRAP; x.border = BD
        a.font = Font(name=FONT, size=14, bold=True, color=DARK)
        ws.row_dimensions[i].height = 60
    head(ws, 2, ["項目", "說明"], [18, 110])
    page(ws, 2, freeze="A3")

    # --- 條件表 ---
    ws = wb.create_sheet("條件表")
    cols = ["分類", "欄位", "說明", "東山街範例", "填寫值", "必填", "沒填時", "設定鍵"]
    title(ws, "排水設計 案件條件表", len(cols))
    head(ws, 2, cols, [10, 30, 34, 40, 36, 8, 30, 34])
    r = 3
    dv = DataValidation(type="list", formula1='"EG,SG"', allow_blank=True); ws.add_data_validation(dv)
    for row in ROWS:
        if row[1] is None:
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(cols))
            x = ws.cell(row=r, column=1, value=row[0])
            x.font = Font(name=FONT, size=18, bold=True, color=DARK); x.fill = SEC_FILL; x.alignment = WRAP
            ws.row_dimensions[r].height = 30; r += 1; continue
        cat, name, desc, ex, key, req, miss = row
        vals = [cat, name, desc, ex, None, req, miss, key]
        for c, v in enumerate(vals, 1):
            x = ws.cell(row=r, column=c, value=v)
            x.font = Font(name=FONT, size=14, color=DARK, bold=(c == 2)); x.alignment = WRAP; x.border = BD
            if c == 5: x.fill = IN_FILL
            if c == 6: x.alignment = CENTER
        if key == "design.ground": dv.add(ws.cell(row=r, column=5))
        fit_height(ws, r, len(cols))
        r += 1
    page(ws, len(cols))

    # --- 側溝與集水井 ---
    ws = wb.create_sheet("側溝與集水井")
    title(ws, "側溝與集水井明細（每條／每座一列）", len(ITEMS_HEAD))
    head(ws, 2, ITEMS_HEAD, [11, 13, 11, 16, 16, 14, 14, 18, 40, 22])
    fit_height(ws, 2, len(ITEMS_HEAD))
    for i, row in enumerate(ITEMS_EX, 3):
        for c, v in enumerate(row, 1):
            x = ws.cell(row=i, column=c, value=v)
            x.font = Font(name=FONT, size=14, color="7A8794", italic=True); x.alignment = CENTER; x.border = BD
        fit_height(ws, i, len(ITEMS_HEAD))
    for i in range(3 + len(ITEMS_EX), 3 + len(ITEMS_EX) + 12):
        for c in range(1, len(ITEMS_HEAD) + 1):
            x = ws.cell(row=i, column=c); x.border = BD; x.fill = IN_FILL
            x.font = Font(name=FONT, size=14, color=DARK); x.alignment = CENTER
        ws.row_dimensions[i].height = 30
    kind = DataValidation(type="list", formula1='"側溝,集水井"', allow_blank=True); ws.add_data_validation(kind)
    kind.add(f"C{3 + len(ITEMS_EX)}:C{3 + len(ITEMS_EX) + 11}")
    page(ws, len(ITEMS_HEAD))

    # --- 停點確認 ---
    ws = wb.create_sheet("停點確認")
    cols = ["序", "停點", "Claude 回報內容", "對應 SKILL／規則", "確認結果", "確認日期"]
    title(ws, "★停點確認紀錄", len(cols))
    head(ws, 2, cols, [6, 22, 40, 32, 30, 16])
    for i, row in enumerate(STOPS, 3):
        for c, v in enumerate(list(row) + [None, None], 1):
            x = ws.cell(row=i, column=c, value=v)
            x.font = Font(name=FONT, size=14, color=DARK); x.alignment = WRAP if c in (3, 4) else CENTER; x.border = BD
            if c >= 5: x.fill = IN_FILL
        fit_height(ws, i, len(cols))
    page(ws, len(cols))

    wb.save(out)
    print(f"已產生：{out}（條件 {sum(1 for x in ROWS if x[1])} 項）")


if __name__ == "__main__":
    main(sys.argv[1])
