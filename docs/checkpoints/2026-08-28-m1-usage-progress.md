# M1 kullanım ilerlemesi checkpoint'i

- Checkpoint issue: #25
- Base / rollback SHA: `d3ed23d736c47ef2e16515965847325d884812aa`
- Hedef sürüm: `v0.7.1`
- Kapsam: `GET /usage-progress` salt-okunur aggregate kontratı

## Gizlilik sınırı

Endpoint yalnız dört aggregate alan döndürür: `distinct_days`, `target_days`, `remaining_days`, `complete`. Harcama satırı, tarih listesi, tutar, kategori ve açıklama dönmez. Canlı doğrulama kanıtı gerçek gün sayılarını yayımlamaz.

## Doğruluk sınırı

Bu endpoint M1'in 14 farklı kullanım günü koşulunu ölçer; M1'i otomatik kapatmaz. Son kamuya açık kanıt `3/14` olarak kalır ve private sonuçtan ROADMAP'e sayı taşınmaz. M5 ile M3.3 kapsam dışıdır.

## Kabul kanıtı

### Özellik PR'si #26

- Final head: `129899dd31e89e165f645c6581e14ab6a61b2a1c`
- CI run: `33207614329`
- Python 3.11 job: `98972581062` — success
- Python 3.12 job: `98972581051` — success
- Python 3.13 job: `98972580806` — success
- Bağımsız QA: `PASS` (conversation `84829ffc-2a55-4011-a374-11b21e7e6b19`)
- Squash merge: `b0f1cca22d2cb9c75562b9312561165ee54af46e` (`2026-08-28T20:19:11Z`)

### İlk canlı doğrulama

- Run: `33207721135`
- Job: `98972947992`
- Sonuç: `Failure`; süre `14s`; exit code `1`
- Artifact veya yeni bot commit'i oluşmadı.
- Exact kök neden log erişimi olmadığı için bilinmiyor; olasılıklar gerçek neden olarak kaydedilmedi.

### Kanıt bağlı yeniden tetikleme PR'si #27

- Final head: `5c210e093d4f6d7c28a557a628369089e7fd196c`
- CI run: `33208038927`
- Python 3.11 job: `98974038009` — success
- Python 3.12 job: `98974037968` — success
- Python 3.13 job: `98974037750` — success
- Exact diff: `.github/workflows/verify-live.yml` içinde yalnız bir açıklayıcı yorum satırı; runtime ve doğrulama mantığı değişmedi.
- Squash merge: `d4ff9fd55ad6252398f8eea251de870f403b9447` (`2026-08-28T20:25:25Z`)

### Başarılı canlı kabul

- Workflow run: `33208165567` — `Success` (`16s`)
- Verify job: `98974471031` — `Success` (`13s`)
- Tetikleme commit'i: `d4ff9fd55ad6252398f8eea251de870f403b9447`
- Kalıcı artifact commit'i: `e9091da49fb95a0fbcc78bc7636fa3d8eb38c59e`
- Artifact timestamp: `2026-08-28T20:25:33Z`
- `/health`: HTTP `200`, `status=ok`, `version=0.7.1` — PASS
- `/history.svg`, `/card.svg`, `/export.csv` — PASS
- `/usage-progress`: HTTP `200`; exact alanlar, türler, hedef ve clamp kontratı — PASS
- Final artifact sonucu: `SONUC: PASS`

Kanıt yalnız kontrat ve güvenli metadata taşır; gerçek `distinct_days` veya `remaining_days` değerlerini yayımlamaz. Bu feature checkpoint'i ancak issue #25'in kendi kabul kriterleri madde bazında doğrulandıktan sonra kapanabilir. M1 kapanmaz: kamuya açık gösterge `3/14` kalır; ilk kişisel enflasyon sonucu ve M1 Done koşullarının tümü ayrıca doğrulanmalıdır.
