# 台灣商管研討會資訊站

這是一個靜態網站，用來追蹤台灣商管領域研討會資訊。前端讀取 `data/conferences.json`，提供關鍵字、舉辦年月、地點、投稿截止日與發表形式篩選，也可依最近更新、舉辦日期、投稿截止日或名稱排序。

## 本機執行

```bash
python3 scripts/update_conferences.py
python3 -m http.server 5173
```

開啟 `http://localhost:5173`。

執行測試與資料驗證：

```bash
python3 -m unittest discover -s tests -t . -v
python3 scripts/update_conferences.py --validate-only
node --check assets/app.js
```

## 每日更新

`.github/workflows/update-conferences.yml` 會每天台北時間 05:15 執行：

1. 讀取 `data/sources.json` 的已知研討會來源。
2. 抓取會議主頁並計算內容雜湊。
3. 將 `data/recurring.json` 的常態性研討會官方管道併入主辦單位來源，透過主辦單位或會議官方網站搜尋年度更新。
4. 掃描主辦單位或會議官方網站的追蹤頁，發現疑似新研討會時建立「待確認」候選。
5. 比對外部研討會彙整站、SSRN 研討會索引與 AFA 公開行事曆；只有明確標示在台灣舉辦的商管活動才建立「待確認」候選。
6. 候選項目需通過正式研討會初步篩選，排除講座、課程、工作坊、招生、期刊專刊、得獎名單等非徵稿研討會內容。
7. 若來源頁內容和前次不同，將該研討會標示為 `[NEW!]` 與「資訊異動」。
8. 回寫 `data/conferences.json` 與 `data/history.json`。
9. 讀取仍開啟的 `[資料回報]` Issue，重新搜尋官方來源；可安全驗證的修正會併入當日更新、回覆並關閉 Issue，仍無法確認者保留至隔日重試。

來源錯誤會寫入 `health` 與個別研討會的 `check_status`。排程仍會保存通過結構驗證的資料，但工作結果會標示失敗，避免部分抓取失敗被誤認為完整成功。日期搜尋年份會依台北時間自動涵蓋本年及次年。

資料來源刻意不使用新聞、媒體報導或一般搜尋結果；所有正式資料應以主辦單位官網、會議官網或主辦單位官方追蹤頁為準。若主辦單位官網直接連到 Google Sites 等外部會議頁，會先列為「待確認」候選。外部彙整站只用來輔助每日比對與提醒，新增項目仍會以「待確認」狀態呈現，確認後才應補進正式研討會來源。

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
- `submission_fee`
- `registration_fee`
- `fields`
- `presentation_formats`
- `attention_notes`

`presentation_formats` 可使用 `oral`、`poster`、`online`、`other`。

`submission_fee` 用於投稿、審稿或論文處理費；`registration_fee` 用於註冊、報名或登記費。請保留官方公告的幣別、金額與適用身分，例如 `一般作者 NT$2,000；學生 NT$1,500`。空字串代表未公告，前端會顯示「未公告」。

## 待確認候選

自動發現的資料保存在 `data/candidates.json`，不會計入正式研討會統計。人工審查時可調整：

- `candidate_status: pending`：顯示於待確認區。
- `candidate_status: rejected`：保留判斷紀錄但不顯示。
- `candidate_status: promoted`：代表已人工確認；仍應將完整資料加入 `data/sources.json`。
- `review_notes`：記錄接受或拒絕原因。

## 使用者回報與自動修正

每張研討會卡片都有「回報資料問題」按鈕。使用者填寫後會開啟預先帶入研討會 ID 的 GitHub Issue；`.github/workflows/process-feedback.yml` 會：

1. 將原始回報保存成 `data/reports/issue-<編號>.json`，避免多筆回報互相覆蓋。
2. 驗證建議網址是否可連線且符合官方網域規則，或確認日期／地點確實出現在主辦單位佐證頁。若回報只指出報名或投稿連結錯誤，系統會先從同一官方網域搜尋明確對應的連結，再套用相同驗證規則。
3. 對可安全驗證的修正建立 PR；無法驗證的內容只記錄並等待人工處理。
4. 回覆原 Issue，附上驗證結果與修正 PR。
5. 將回報、驗證結果與 PR 寄到 `ftsainfu@gmail.com`。

寄信前，請在 GitHub repository 的 `Settings → Secrets and variables → Actions` 設定：

- `SMTP_APP_PASSWORD`：`ftsainfu@gmail.com` 啟用兩步驟驗證後建立的 Gmail App Password，不是一般登入密碼。
- `SMTP_USERNAME`（選用）：若寄件帳號不是 `ftsainfu@gmail.com` 才需要設定。

若尚未設定密鑰，Issue、驗證與修正 PR 仍可運作，只會略過寄信。

Repository 的 Actions 設定也需開啟「Allow GitHub Actions to create and approve pull requests」，工作流程才能自動建立修正 PR。

## 部署

此專案不需要建置步驟，可直接用 GitHub Pages、Vercel 或任何靜態網站服務部署。若使用 GitHub Pages，將 Pages 指向 `main` 分支根目錄即可。工作流程使用完整 commit SHA 鎖定第三方 Action，並設有測試、執行逾時與同時執行保護。

## 常態追蹤

`data/recurring.json` 收錄定期舉辦的商管、財金、行銷、永續與決策管理類研討會官方管道。這些項目不一定代表最新年度已開放投稿；每日更新會把它們當作主辦單位搜尋來源，若發現符合正式研討會條件的新年度公告，會先列為「待確認」候選。
