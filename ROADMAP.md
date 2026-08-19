# ROADMAP — tek doğruluk kaynağı

> Her oturuma buradan başlanır. "Şu an neredeyiz?" sorusunun cevabı bu dosyadır.
> Durum etiketleri: `planned` → `implemented` → `tested` → `verified` → `deployed`.

## ŞU AN NEREDEYİZ

**Aşama:** M3 — bağımlılık döngüsü (2026-08-19).
**Son biten:** M3.1 **verified** (2026-08-19) — canlı `/export.csv` Actions kanıtıyla doğrulandı (`artifacts/live-history-verify.txt`, bot commit `efb4b31`: /health 200 v0.5.0, /export.csv HTTP 200 + BOM `efbbbf` + tam başlık + `text/csv`, SONUC: PASS). İlk koşu FAIL'di: Render henüz v0.4.0'daydı (404) → deploy sonrası yeniden tetiklendi. QA zorunlu bulgusu: kişisel veri içerebilecek uçların gövdesi kanıt dosyasına asla yazılmaz — yalnız metadata (kod/boyut/hexhead/boolean).
**Sıradaki iş:** M3.2 TÜİK açıklama günü bildirimi (tasarım kararı bekliyor) ve 14 gün harcama girişi (M1 Done kapanışı, ~2026-09-01).
**Açık güvenlik borcu:** Neon şifresi sohbete düştü → reset password + Render `DATABASE_URL` + GitHub secret `LIVE_DATABASE_URL` güncellemesi.

## Milestone'lar

### M1 — Dikey dilim (hedef: 2 hafta, bitiş ~2026-09-01)

Tek akış: harcama gir → ay sonunda kişisel endeks + TÜİK kıyası tek ekranda.

| # | İş | Kabul kriteri | Durum |
|---|---|---|---|
| M1.1 | FastAPI iskeleti + `/health` + CI (pytest+ruff) | CI yeşil, endpoint 200 döner | verified |
| M1.2 | PostgreSQL şeması: `expenses`, `categories`, `official_cpi` | migration koşuyor, testli CRUD | verified |
| M1.3 | Harcama giriş formu (tek sayfa web UI) | tarayıcıdan harcama eklenebiliyor | verified |
| M1.4 | TÜİK/EVDS TÜFE ingestion job | son 24 ay TÜFE DB'de, idempotent | verified |
| M1.5 | Kişisel endeks hesap motoru (Laspeyres) | birim testli, elle doğrulanmış örnek | verified |
| M1.6 | Kıyas ekranı: "senin %Y vs resmi %X" | tek ekranda iki sayı | verified |
| M1.7 | Deploy (Render free + Neon PG + Actions cron) | telefondan URL ile erişilebiliyor | deployed |

**M1 Done tanımı:** Umut 14 gün kendi harcamasını girmiş ve app ilk kişisel
enflasyon sayısını göstermiş durumda; deploy canlı; CI yeşil.

### M2 — Veri derinliği

| # | İş | Kabul kriteri | Durum |
|---|---|---|---|
| M2.1 | Kategori bazlı alt endeksler (13 ECOICOP bölümü, EVDS `bie_tukfiy2025`) | kişisel ≠ resmi ayrışması canlıda görünür; eşleşmeyen kategori `*` ile manşete düşer | **verified** (canlı: %23.05 ≠ %31.75, 2026-08-18) |
| M2.2 | Aylık özet kartı (paylaşılabilir görsel) | `/card.svg` 800x418 sosyal medya kartı döner (kişisel vs resmi + fark + top-3 kategori); veri eksikliğinde 500 vermez, Türkçe ipucu kartı döner | **verified** (canlı screenshot: %23.05 vs %31.75 + top kategoriler + v0.3.0, 2026-08-19) |
| M2.3 | Harcama geçmişi grafiği | `/history.svg` son 12 ayın aylık toplamlarını çubuk grafikle döner; sıfır ek bağımlılık; veri yokken Türkçe ipucu, asla 500; ana sayfaya gömülü | **verified** (Actions canlı kanıtı `artifacts/live-history-verify.txt`, 2026-08-19) |

### M3 — Bağımlılık döngüsü

| # | İş | Kabul kriteri | Durum |
|---|---|---|---|
| M3.1 | Veri dışa aktarma (CSV) — veri kilidi dürüstlüğü | `/export.csv` tüm harcamaları kategori adıyla tarih sırasında indirir; UTF-8 BOM (Excel-TR), RFC 4180 CRLF, `Content-Disposition: attachment`, CSV injection savunması; boş DB/hata durumunda header-only, asla 500 | **verified** (canlı Actions kanıtı, bot commit `efb4b31`, 2026-08-19) |
| M3.2 | TÜİK açıklama günü bildirimi ("resmi %X çıktı, seninki %Y") | açıklama günü tespit + bildirim kanalı; tasarım kararı bekliyor | planned |
| M3.3 | Parquet dışa aktarma | bilinçli ertelendi — karar kaydına bakınız | deferred |

## Karar kaydı

| Tarih | Karar | Gerekçe |
|---|---|---|
| 2026-08-18 | Proje seçildi: kişisel enflasyon app'i | Ekonomi kimliğiyle eşleşme, gerçek acı frekansı (haftalık alışveriş), veri kilidi savunulabilirliği |
| 2026-08-18 | Web-first (FastAPI + PG), mobil store yok | Öğrenme maliyeti ve deploy hızı; telefonda tarayıcı yeterli |
| 2026-08-18 | OCR/ML kapsam dışı (M1) | Dikey dilim disiplini — önce çalışan döngü |
| 2026-08-18 | App adı: "Enflasyonumdan ne haber?" (repo slug: `enflasyonum`) | URL/import uyumluluğu; marka adı README'de |
| 2026-08-18 | ORM: SQLAlchemy 2.0 + Alembic; para alanları `Numeric` (asla float) | Migration disiplini + kuruş hassasiyeti (float yuvarlama hatası enflasyon hesabını bozar) |
| 2026-08-18 | CI testleri gerçek PostgreSQL 16 servis konteynerine karşı koşar | "SQLite'ta geçti, PG'de patladı" sınıfı hataları CI'da yakalamak |
| 2026-08-18 | POST sonrası 303 redirect (PRG deseni) | F5 çift kayıt üretmesin; form UX'in temel disiplini |
| 2026-08-18 | Tutar girişinde virgül desteği (`42,50` → `42.50`) | TR kullanıcı klavye alışkanlığı; Decimal'e normalize edilir |
| 2026-08-18 | ~~TÜFE kaynağı: TCMB EVDS API, seri `TP.FG.J0` (2003=100, aylık)~~ **GÜNCELLENDİ ↓** | Resmi kaynak, ücretsiz, JSON; TÜİK sitesinde stabil API yok |
| 2026-08-18 | **TÜFE serisi `TP.TUKFIY2025.GENEL` (2025=100, grup `bie_tukfiy2025`)** — TÜİK Ocak 2026'da temel yılı değiştirdi (ECOICOP v2), eski seri 2026-01'de kesildi (son değer 3683.83). Yeni seri geçmişe dönük değerleri de içerdiğinden zincirleme gerekmedi. Keşif canlı EVDS metadata sorgusuyla yapıldı: `artifacts/evds-discovery.txt` | Canlı koşu 18/24 dönem dönünce kök neden analizi; tek seriyle temiz çözüm |
| 2026-08-18 | `index_value` hassasiyeti `Numeric(14,6)` (migration 0002) | 2025=100 serisi 6 ondalık taşıyor; `Numeric(12,4)` Postgres'te sessizce yuvarlıyordu — CI'ın gerçek PG'de koşması bu hatayı yakaladı |
| 2026-08-18 | Ingest'te fetch/parse ayrımı; CI'da canlı API çağrısı yok (MockTransport) | Parser ağsız test edilir; dış servise bağımlı test flaky + secret riski |
| 2026-08-18 | EVDS anahtarı `EVDS_API_KEY` env'den, HTTP `key` header'ında | Secret koda/repoya girmez; EVDS anahtarı query'de değil header'da ister |
| 2026-08-18 | Canlı doğrulama deseni: workflow edit-push → Actions koşusu → sonuç `artifacts/*.txt` olarak bot commit'i | Umut'un lokal ortamı yok; tüm canlı kanıtlar repo içinde, tekrarlanabilir |
| 2026-08-18 | Kişisel endeks = harcama-ağırlıklı Laspeyres: baz ay kategori harcamaları (w_i) × resmi fiyat görelileri (R_i); `L = 100·Σ(w_i·R_i)/Σ(w_i)`. M1'de tüm kategoriler manşet TÜFE görelisine düşer; `category_relatives` parametresi M2 ECOICOP alt endekslerine hazır | Harcama kaydında miktar/birim fiyat yok → madde bazlı Laspeyres hesaplanamaz; ONS/Eurostat kişisel enflasyon hesaplayıcılarıyla aynı yöntem, motor M2'de değişmeden kalır |
| 2026-08-18 | Kıyas penceresi = son resmi TÜFE dönemi vs 12 ay öncesi (yıllık); sepet ayı ≠ baz ayı — motora geriye-uyumlu `weights_period` parametresi eklendi (ağırlıklar kullanıcının son harcama ayından, göreli resmi pencereden) | Resmi TÜFE ~1 ay geriden yayımlanır; kullanıcının güncel sepeti pencere baz ayına denk gelmez. Kıyas bloğu asla 500 vermez: veri eksikse Türkçe ipucu gösterilir. M1'de iki sayı eşittir (manşet fallback) — ekranda açıkça not edildi, M2'de ayrışır |
| 2026-08-18 | Deploy: Render free (web, blueprint) + Neon free (PG) + GitHub Actions cron (günlük ingest 07:30 UTC) | Fly.io CLI ister → lokal ortam yok, elenir; Render/Neon tamamen web UI. Render cron ücretli → ücretsiz Actions cron, desen zaten kurulu. Neon URL öneki `postgresql+psycopg://` yapılmalı (psycopg3). Ödünleşim: free instance ~15 dk'da uyur, ilk istek 30–60 sn |
| 2026-08-18 | **M1.7 deployed:** canlı URL https://enflasyonum-7gcn.onrender.com — kanıt: deploy logunda `/health` 200 + ilk manuel daily-ingest yeşil. İlk deploy denemesi kırmızıydı: Render blueprint `sync:false` env değişkenini sormadı → `DATABASE_URL` elle Environment'a girildi; ayrıca ilk ingest koşusu secret'a çift-şemalı URL yapıştırıldığı için düştü, secret düzeltilince yeşil | Deploy iki bağımsız kanıtla kapatılır: health ucu + zamanlanmış iş. Neon şifresi sohbete düştü → reset password borcu kayda geçirildi |
| 2026-08-18 | **M1.5+M1.6 verified:** Umut canlı URL'de gördü (ekran görüntüsü): %31.75 vs %31.75, pencere 2025-07 → 2026-07, sepet 2026-08 (gıda 50 TL %100), "Bu ayın toplamı: 50.00 TL". Canlı Neon DB'de gerçek EVDS verisiyle hesap doğru çalışıyor | `verified` = gerçek kullanıcı, gerçek veri, gerçek ortam. Yıllık %31.75, EVDS 2025-07→2026-07 penceresinin gerçek değeri |
| 2026-08-18 | **M2.1 (PR #9, `a7bd34f`):** 13 ECOICOP bölüm alt endeksi — EVDS `bie_tukfiy2025` grubundan `TP.TUKFIY2025.01`–`.13`; kategori adı → bölüm eşlemesi ~60 anahtarlık Türkçe sözlükle exact-match (`series.py`), eşleşmeyen kategori manşete düşer ve ekranda `*` ile işaretlenir; `official_cpi` benzersizliği `(series_code, period)` oldu (migration 0003, SQLite batch + PG constraint drop); ingest tek koşuda 14 seri çeker. Türkçe İ tuzağı: `"KOZMETİK".lower()` → `kozmeti̇k` (U+0307) ≠ `kozmetik` — normalizasyon app yazım katmanında, testte büyük-İ vakası bilinçli dışarıda | Ürünün varlık sebebi "senin enflasyonun farklı" iddiası; manşet-fallback ile iki sayı hep eşitti. Exact-match sözlük fuzzy eşlemeden öngörülebilir; yanlış pozitif eşleme yanlış endeksten kötüdür. `*` işareti hesap şeffaflığı ilkesinin devamı |
| 2026-08-18 | **M2.1 verified:** Umut daily-ingest'i elle tetikledi (14 seri Neon'a indi), canlı ekran görüntüsü: kişisel **%23.05** vs resmi **%31.75** (fark -8.70 puan; kozmetik 551 TL + gıda 50 TL sepeti). Kozmetik alt endeksi (bölüm 13) son 12 ayda manşetten yavaş artmış → ürün iddiası üretimde kanıtlandı | `verified` = gerçek kullanıcı + gerçek sepet + gerçek EVDS alt serileri. İlk canlı ayrışma kanıtı; ekranda `*` yok = her iki kategori de kendi alt endeksiyle eşleşti |
| 2026-08-19 | **M2.2 (PR #11, `ff6308f`):** paylaşılabilir aylık özet kartı `/card.svg` — SVG saf string olarak üretilir, sıfır ek bağımlılık (matplotlib yok, Render free build hafif kalır); 800x418 (~1.91:1 sosyal medya oranı), koyu tema; kişisel vs resmi + fark + top-3 kategori; kullanıcı metinleri XML escape; veri eksikliğinde 500 yerine Türkçe ipucu kartı; `image/svg+xml` + `Cache-Control: no-store`. 7 test, v0.3.0. QA notu: boyut/viewBox, ipucu escape, fallback Cache-Control, top-3 sınırı ve yıldızsız satır assertion'ları eksik — M2.3 öncesi eklenecek | Kart üretimi saf string işlemi olunca ağsız/başsız (headless) test edilebilir; görsel kütüphane bağımlılığı free-tier build'i şişirirdi. Paylaşım, M3 bağımlılık döngüsünün ilk tuğlası |
| 2026-08-19 | **CI kendi kendini raporlar:** Actions loglarına sandbox'tan erişim yok → ci.yml'a fail anında `pip check + ruff + alembic + pytest` özetini PR'a yorum yazan debug adımı eklendi (`permissions: pull-requests: write` gerekti). İlk kullanımında kök nedeni buldu: ruff F541 (card.py başlıkta placeholder'sız f-string) — testlerin 58/58 geçtiği, tek sorunun lint olduğu bu yorumdan anlaşıldı | Log erişimi olmayan ortamda CI kör kutuydu; teşhis aracın yoksa teşhisi boru hattına göm. Kalıcı altyapı kazanımı |
| 2026-08-19 | **M2.2 verified:** Umut canlı `/card.svg`'yi tarayıcıda açtı (ekran görüntüsü): başlık "Enflasyonumdan ne haber?", kişisel **%23.05** vs resmi **%31.75**, fark -8.70 puan, pencere 2025-07 → 2026-07, sepet 2026-08, kozmetik %91.68 pay (enflasyonu %21.74) + gıda %8.32 pay (enflasyonu %37.53), footer `enflasyonum v0.3.0`. Yıldız yok = tam kategori eşleşmesi; Render auto-deploy sorunsuz | `verified` = gerçek kullanıcı + gerçek veri + gerçek ortam. Kategori payları ve alt enflasyonlar kartta doğru render edildi — M2.2 tamamen kapandı |
| 2026-08-19 | **M2.3 (PR #12):** harcama geçmişi grafiği `/history.svg` — aylık toplama SQL yerine Python tarafında: testler SQLite'ta, üretim PG'de koşuyor ve ay bazlı SQL (date_trunc/strftime) iki motorda farklı; kişisel ölçekte satır sayısı küçük, Decimal korunur (para asla float). SVG kartla aynı saf-string desen, 800x360, son 12 ay `MAX_MONTHS` sabitiyle sınırlı. Aynı PR'da M2.2 QA borcu kapandı: 5 kart sözleşme testi eklendi. v0.4.0 | Taşınabirlik > SQL zarafeti bu ölçekte; toplama fonksiyonu saf olunca birim testi ağsız. Sözleşme testleri boyut/escape/cache gibi kırılgan kontratları gelecek refactor'lara karşı kilitler |
| 2026-08-19 | **verify-live Actions deseni kalıcılaştı (`.github/workflows/verify-live.yml`):** kendi dosyasına push + workflow_dispatch tetikleyicili workflow, canlı URL'yi `curl --retry 6 --retry-delay 20` ile yoklar (Render cold start), sonucu `artifacts/live-history-verify.txt` içine `SONUC: PASS|FAIL` bloğuyla yazar ve `[skip ci]` bot commit'i olarak main'e işler. M2.3 bu desenle `verified` oldu (bot commit `d0f074c`) | Sandbox'tan dış ağa çıkış yok, Umut'un lokal ortamı yok → canlı doğrulama kanıtı ancak Actions üzerinden repo içine akar; desen tekrarlanabilir, sonraki uçlar için probu genişletmek yeter |
| 2026-08-19 | **M3.1 (PR #13, v0.5.0):** dışa aktarma formatı CSV, Parquet bilinçli ertelendi (M3.3 `deferred`): pyarrow bağımlılığı Render free-tier build disiplinine aykırı, CSV her araçta açılır. Saf fonksiyon `expenses_to_csv` BOM'suz taşınabilir CSV üretir; UTF-8 BOM (Excel-TR uyumu) HTTP teslim katmanında (route) eklenir — taşıma katmanı sorumluluğu. QA (DenetiQA) ilk turda FAIL verdi: CSV injection açığı → `=`,`+`,`-`,`@`,TAB,CR önekli kullanıcı metinleri `'` ile nötralize edildi (OWASP); pyproject sürüm eşitlemesi ve ROADMAP güncellemesi aynı PR'a alındı. 14 export testi | Veri kilidi dürüstlüğü ürün ilkesi: kullanıcı verisini rehin tutmayız. Injection savunması saf fonksiyonda: her çağrı yolu (gelecekteki CLI/cron dahil) otomatik korunur; yalnız serbest metin kolonları defuse edilir ki sayısal kolonlar bozulmasın |
| 2026-08-19 | **M3.1 verified + kanıt hijyeni kuralı:** verify-live.yml'a `/export.csv` probu eklendi. QA zorunlu bulgusu: kişisel harcama verisi içerebilecek ucun gövdesi repoya commit edilen kanıt dosyasına ASLA yazılmaz → yalnız güvenli metadata loglanır (HTTP kodu, boyut, ilk 3 baytın hex'i, content-type/başlık boolean'ları). Kriterler: 200 + BOM `efbbbf` + ilk satır tam `tarih,kategori,aciklama,tutar` + `text/csv`. İlk koşu FAIL: Render henüz v0.4.0 servis ediyordu (/export.csv 404) — deploy tamamlanınca yeniden tetiklendi, ikinci koşu **SONUC: PASS** (bot commit `efb4b31`, /health v0.5.0) | Doğrulama altyapısı veri sızıntısı kaynağına dönüşmemeli; kanıt = türetilmiş metadata, asla kullanıcı verisi. İlk FAIL gerçek bir yarış durumunu yakaladı: merge ≠ deploy — canlı doğrulama deploy'un bitmesini beklemeli |
