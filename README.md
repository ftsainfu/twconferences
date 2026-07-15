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
3. 檢查正式收錄研討會的 `homepage_url`、`submission_url`、`registration_url`；結果寫入 `data/history.json` 的連結健康紀錄，連續 2 次失敗才標示為可能失效。
4. 將 `data/recurring.json` 的常態性研討會官方管道併入主辦單位來源，透過主辦單位或會議官方網站搜尋年度更新。
5. 掃描主辦單位、會議官方網站、`university_sources` 中的大學商管學院、`scholarly_sources` 中的期刊／學會，以及 `government_sources` 中的政府活動公告，發現疑似新研討會時建立「待確認」候選。
6. 比對外部研討會彙整站、SSRN 研討會索引與 AFA 公開行事曆；只有明確標示在台灣舉辦的商管活動才建立「待確認」候選。
7. 候選項目需通過正式研討會初步篩選，排除講座、課程、工作坊、招生、單純期刊／專刊徵稿、得獎名單等非研討會內容。
8. 同一研討會若由多個來源發現，會依網址、標題與年度合併，保留各佐證來源及不同網域的交叉核對數，不重複顯示。
9. 若來源頁內容和前次不同，將該研討會標示為 `[NEW!]` 與「資訊異動」。
10. 依官方來源、日期地點、投稿方式、發表資訊、報名與費用資訊計算「資料完整度」星等，回寫 `data/conferences.json` 與 `data/history.json`。
11. 讀取仍開啟的 `[資料回報]` Issue，重新搜尋官方來源；可安全驗證的修正會併入當日更新、回覆並關閉 Issue，仍無法確認者保留至隔日重試。
12. 讀取 `[研討會評分]` Issue，並在已設定外部評分 API 時同步讀取免登入評分資料，去除重複評分後產生 `data/ratings.json`。

來源錯誤會寫入 `health` 與個別研討會的 `check_status`；連結連續失敗會寫入 `link_health` 並在頁面提示。排程仍會保存通過結構驗證的資料，但工作結果會標示失敗，避免部分抓取或連結失效被誤認為完整成功。日期搜尋年份會依台北時間自動涵蓋本年及次年。`[NEW!]` 目前代表 `last_changed` 或 `created_at` 在 14 天內。

資料來源刻意不使用新聞、媒體報導或一般搜尋結果；所有正式資料應以主辦單位官網、會議官網或主辦單位官方追蹤頁為準。若主辦單位官網直接連到 Google Sites 等外部會議頁，會先列為「待確認」候選。外部彙整站只用來輔助每日比對與提醒，新增項目仍會以「待確認」狀態呈現，確認後才應補進正式研討會來源。

`data/sources.json` 的 `university_sources` 專門收錄台灣商學院／管理學院官方首頁。這類來源採較短逾時且不重試，避免單一院校拖慢每日更新；院校官網連出的外部會議網站可成為候選，但表單與社群網站不會直接作為會議證據。候選會保留 `discovered_from_url`，方便回查是哪一個院校官網發現。

`scholarly_sources` 收錄期刊與學會官方網站，使用相同的短逾時與正式研討會篩選。期刊網站可能轉載海外活動，因此可針對來源設定 `require_taiwan_marker: true`，只有標題或網址明確出現台灣地名時才建立候選。

`government_sources` 收錄國科會等政府官方活動列表，支援以 `urls` 指定完整分頁。政府公告只作為發現與交叉佐證；醫學、理工、語文、課程、補助辦法等不符合本站商管範圍的內容會排除，正式收錄仍須回到主辦單位或會議官網核對。

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
- `submission_deadline_previous`
- `submission_deadline_status`
- `acceptance_notification_date`
- `submission_fee`
- `registration_fee`
- `publication_opportunities`
- `fields`
- `presentation_formats`
- `attention_notes`

`presentation_formats` 可使用 `oral`、`poster`、`online`、`other`。

`submission_fee` 用於投稿、審稿或論文處理費；`registration_fee` 用於註冊、報名或登記費。請保留官方公告的幣別、金額與適用身分，例如 `一般作者 NT$2,000；學生 NT$1,500`。空字串代表未公告，前端會顯示「未公告」。

`publication_opportunities` 用於會議明確公告的合作期刊、專刊或會後轉投機會；每筆可包含 `journal_name`、`journal_url`、`submission_url` 與 `notes`。只有在會議或期刊官方頁可核對時才填寫，不把單純刊登會議消息誤認為保證刊登。

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

## 星等與參加者推薦

每張正式研討會卡片會分別顯示：

- `資料完整度`：系統依五項客觀資料條件計算，不代表研討會學術聲望。
- `參加者推薦`：已報名或已參加者提供的 1–5 星推薦度，並可展開查看五個面向平均。

「評分推薦度」優先使用免登入評分 API；未設定或暫時失敗時，會開啟預填的 GitHub Issue 作為備援。使用者仍須確認本人已報名或參加；此機制屬身分聲明，無法驗證實際繳費或出席紀錄。新評分必須提供整體推薦、五個面向評分及至少 20 字原因：

- 議程／主題品質
- 投稿與審查透明度
- 主辦單位溝通與行政效率
- 交流與人脈價值
- 費用／時間投入是否值得

免登入評分的設定分成兩段：

1. 前端送出：將 Google Apps Script 或其他評分 API 網址填入 `data/site_config.json` 的 `rating_api_url`。若 API 需要瀏覽器 `no-cors` 模式，將 `rating_api_mode` 改為 `no-cors`；否則維持 `cors`。
2. 每日彙整：在 GitHub repository 的 `Settings → Secrets and variables → Actions` 設定 `RATING_API_URL` 與 `RATING_READ_TOKEN`，每日更新就會抓取外部評分並和 GitHub Issue 評分一起產生 `data/ratings.json`。

可直接使用 `scripts/rating_webapp.gs` 作為 Google Apps Script Web App 範本：

1. 建立 Google Sheet。
2. 開啟 Apps Script，貼上 `scripts/rating_webapp.gs`。
3. 在 Apps Script 的 Script Properties 設定 `READ_TOKEN`，值使用一組自行產生的長隨機字串。
4. 部署為 Web App，執行身分選「我」，存取權依需求選「Anyone」或組織內可存取。
5. 將部署後的 `/exec` 網址填入 `data/site_config.json` 的 `rating_api_url`，也填入 GitHub Secret `RATING_API_URL`；`READ_TOKEN` 同步填入 GitHub Secret `RATING_READ_TOKEN`。

外部評分以瀏覽器產生並保存在 localStorage 的 `voter_id` 去除重複；同一瀏覽器對同一研討會只採最新一票。GitHub Issue 備援則以 GitHub 帳號去除重複；`.github/workflows/process-rating.yml` 會驗證格式、重新產生 `data/ratings.json` 並關閉有效評分 Issue。

為降低灌票影響，彙整時會標記可疑票並排除在平均外，但保留 `flagged_count` 供前端提示。現行規則包含同一評分者短期大量評分、不同評分使用完全相同原因、以及缺乏具體說明的極端評分。低於 3 票的研討會會顯示「樣本較少」，避免單一高分造成誤導。

## 年度月份儀表板

「研討會資訊」Tab 以年度切換顯示 1–12 月的投稿截止日與活動舉辦日數量。統計只納入正式收錄項目，候選資料不計入；同一研討會分別依 `submission_deadline` 與 `event_start` 各計入對應月份一次。預設年度使用 `generated_at` 所在年度，並標示兩組資料的高峰月份，提醒使用者在投稿截止高峰前 2–3 個月準備。

儀表板預設使用 `state.filtered`，因此關鍵字、領域、年月、地點、舉辦狀態、投稿期限、投稿狀態、發表形式與英文發表篩選變動時會同步重算。使用者亦可將統計範圍切換為「全部正式收錄」，忽略目前篩選條件查看全體基準。

## 學生研討會獎補助

`data/grants.json` 維護虎科大與國科會學生研討會獎補助資訊，前端顯示申請資格、補助或獎勵內容、期限、應備文件、申請流程、核銷程序及官方連結。

現行與歷史方案必須分開標示。未查得當年度續辦公告的校內專案只能使用 `status: archived`，不得沿用舊年度金額、計畫編號、申請表或截止日。國科會方案的校內收件截止時間由虎科大訂定，頁面不得自行推定，應提示申請人先向研發處確認。

專區的建議順序固定以國科會補助為第一順位，再確認校內專案或經費分攤。資格初篩只檢查公開規則中的基本條件，不得顯示為正式核定結果；國際學生英文說明必須保留「中文辦法及虎科大、國科會審查結果為準」的提示。

虎科大技藝獎金屬獲獎後獎勵，與出席前差旅補助分開。研討會最佳論文、優秀論文或論文競賽獎不得直接視為合格；資料必須提示學生備妥競賽層級、名次、主辦單位、參賽與得獎隊數等證明，並由系所初審及研發處複審認定。

首頁以「研討會資訊」及「獎補助專區」兩個頁面層級 Tab 分流內容。`#grants` 可直接開啟獎補助 Tab，並須保留鍵盤方向鍵切換與正確的 `tablist`、`tab`、`tabpanel` ARIA 關係。

獎補助專區另提供「中文／English」切換。每一筆現行與歷史方案都必須在 `english` 物件中提供完整的資格、金額、期限、文件、流程及提醒，不可只翻譯標題或摘要；外部連結則以 `label_en` 說明目標頁可能仍為中文。

現行方案必須提供明確的直接申請入口：國科會連至學術研發服務網，虎科大技藝獎金連至 eCare；連結文字使用「線上申請／Apply online」與一般辦法、公告連結區分。

## 部署

此專案不需要建置步驟，可直接用 GitHub Pages、Vercel 或任何靜態網站服務部署。若使用 GitHub Pages，將 Pages 指向 `main` 分支根目錄即可。工作流程使用完整 commit SHA 鎖定第三方 Action，並設有測試、執行逾時與同時執行保護。

## 常態追蹤

`data/recurring.json` 收錄定期舉辦的商管、財金、行銷、永續與決策管理類研討會官方管道。這些項目不一定代表最新年度已開放投稿；每日更新會把它們當作主辦單位搜尋來源，若發現符合正式研討會條件的新年度公告，會先列為「待確認」候選。
