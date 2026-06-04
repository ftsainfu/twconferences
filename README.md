# 台灣商管研討會資訊站

這是一個靜態網站，用來追蹤台灣商管領域研討會資訊。前端讀取 `data/conferences.json`，提供關鍵字、舉辦年月、地點、投稿截止日與發表形式篩選，也可依最近更新、舉辦日期、投稿截止日或名稱排序。

## 本機執行

```bash
python3 scripts/update_conferences.py
python3 -m http.server 5173
```

開啟 `http://localhost:5173`。

## 每日更新

`.github/workflows/update-conferences.yml` 會每天台北時間 05:15 執行：

1. 讀取 `data/sources.json` 的已知研討會來源。
2. 抓取會議主頁並計算內容雜湊。
3. 若來源頁內容和前次不同，將該研討會標示為 `[NEW!]` 與「資訊異動」。
4. 從 RSS 搜尋來源建立候選項目，候選項目會標示為「待確認」。
5. 回寫 `data/conferences.json` 與 `data/history.json`。

## 新增或修正研討會

編輯 `data/sources.json` 的 `conferences` 陣列。每筆資料至少應包含：

- `id`
- `title`
- `organizer`
- `homepage_url`
- `submission_url`
- `registration_url`
- `event_start`
- `location`
- `submission_deadline`
- `fields`
- `presentation_formats`
- `attention_notes`

`presentation_formats` 可使用 `oral`、`poster`、`online`、`other`。

## 部署

此專案不需要建置步驟，可直接用 GitHub Pages、Vercel 或任何靜態網站服務部署。若使用 GitHub Pages，將 Pages 指向 `main` 分支根目錄即可。
