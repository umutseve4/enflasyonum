# ROADMAP — tek doğruluk kaynağı

> Her oturuma buradan başlanır. "Şu an neredeyiz?" sorusunun cevabı bu dosyadır.
> Durum etiketleri: `planned` → `implemented` → `tested` → `verified` → `deployed`.

## ŞU AN NEREDEYİZ

**Aşama:** M1 — dikey dilim (2026-08-18).
**Son biten:** M1.6 — kıyas ekranı, **tested** (PR #7, merge `e2ed1dd`, CI 3/3 yeşil, 6 yeni test; toplam 17+ test). `verified` etiketi M1.5+M1.6 için Umut tarayıcıda gerçek veriyle iki sayıyı görünce verilecek (M1.7 deploy sonrası).
**Sıradaki tek iş:** M1.7 — deploy (ücretsiz tier: Fly.io/Render + Neon/Supabase PG).

## Milestone'lar

### M1 — Dikey dilim (hedef: 2 hafta, bitiş ~2026-09-01)

Tek akış: harcama gir → ay sonunda kişisel endeks + TÜİK kıyası tek ekranda.

| # | İş | Kabul kriteri | Durum |
|---|---|---|---|
| M1.1 | FastAPI iskeleti + `/health` + CI (pytest+ruff) | CI yeşil, endpoint 200 döner | verified |
| M1.2 | PostgreSQL şeması: `expenses`, `categories`, `official_cpi` | migration koşuyor, testli CRUD | verified |
| M1.3 | Harcama giriş formu (tek sayfa web UI) | tarayıcıdan harcama eklenebiliyor | verified |
| M1.4 | TÜİK/EVDS TÜFE ingestion job | son 24 ay TÜFE DB'de, idempotent | verified |
| M1.5 | Kişisel endeks hesap motoru (Laspeyres) | birim testli, elle doğrulanmış örnek | tested |
| M1.6 | Kıyas ekranı: "senin %Y vs resmi %X" | tek ekranda iki sayı | tested |
| M1.7 | Deploy (ücretsiz tier: Fly.io/Render + Neon/Supabase PG) | telefondan URL ile erişilebiliyor | planned |

**M1 Done tanımı:** Umut 14 gün kendi harcamasını girmiş ve app ilk kişisel
enflasyon sayısını göstermiş durumda; deploy canlı; CI yeşil.

### M2 — Veri derinliği (taslak)

- Kategori bazlı alt endeksler (gıda/ulaşım/eğlence) — EVDS `bie_tukfiy2025`
  grubu tüm ECOICOP alt kırılımlarını içeriyor (keşif: `artifacts/evds-discovery.txt`);
  motor hazır: `compute_personal_index(category_relatives=...)` kategori
  görelilerini şimdiden kabul ediyor
- Aylık özet kartı (paylaşılabilir görsel)
- Harcama geçmişi grafiği

### M3 — Bağımlılık döngüsü (taslak)

- TÜİK açıklama günü bildirimi ("resmi %X çıktı, seninki %Y")
- Veri dışa aktarma (CSV/Parquet) — veri kilidi dürüstlüğü

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
