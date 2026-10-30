# mbmgi

交付版面與流程圖規則的正本。各台電腦的 Claude 全域設定從這裡同步。

## 檔案

- `CLAUDE.md` — 規則正本。要改規則請開分支、送 PR，不要直接推 `main`（`main` 有分支保護）。
- `sync-rules.ps1` — 把正本同步到本機全域 `~/.claude/CLAUDE.md` 的腳本。

## 新電腦第一次設定

在 PowerShell 跑這兩行（路徑可自行換）：

```powershell
git clone https://github.com/n86951281-collab/mbmgi D:\Claude_工作區\mbmgi
D:\Claude_工作區\mbmgi\sync-rules.ps1
```

如果全域 `~/.claude/CLAUDE.md` 還沒有同步標記，腳本會告訴你要補哪兩行。把這兩行加在檔案最後、中間空一行：

```
<!-- RULES:BEGIN 以下由 sync-rules.ps1 從 GitHub 同步，請勿手改 -->

<!-- RULES:END -->
```

標記以外的內容是那台電腦專屬的（NAS 路徑、檔名前綴等），同步時不會被動到。

## 之後每次更新規則

```powershell
D:\Claude_工作區\mbmgi\sync-rules.ps1
```

腳本會先抓最新的 `main`，再覆蓋標記之間的內容，覆蓋前存一份 `CLAUDE.md.bak`。
跑完要重新開啟 Claude Code，新規則才會生效。
