# ROADMAP — tek doğruluk kaynağı

> Her oturuma buradan başlanır. "Şu an neredeyiz?" sorusunun cevabı bu dosyadır.
> Durum etiketleri: `planned` → `implemented` → `tested` → `verified` → `deployed`.

## ŞU AN NEREDEYİZ

**Aşama:** M1 — dikey dilim (2026-08-18).
**Son biten:** M1.4 — EVDS TÜFE ingestion (PR #4, merge `90d2fae`, CI 3/3 yeşil). Durum `tested`: parser+idempotency+mock HTTP testli; **canlı EVDS çekimi Umut'un API anahtarını beklediği için henüz `verified` değil.**
**Sıradaki tek iş:** M1.5 — kişisel endeks hesap motoru (Laspeyres). Paralel bekleyen: Umut'un EVDS anahtarı → canlı ingest koşusu → M1.4 `verified`.

## Milestone'lar

### M1 — Dikey dilim (hedef: 2 hafta, bitiş ~2026-09-01)

Tek akış: harcama gir → ay sonunda kişisel endeks + TÜİK kıyası tek ekranda.

| # | İş | Kabul kriteri | Durum |
|---|---|---|---|
| M1.1 | FastAPI iskeleti + `/health` + CI (pytest+ruff) | CI yeşil, endpoint 200 döner | verified |
| M1.2 | PostgreSQL şeması: `expenses`, `categories`, `official_cpi` | migration koşuyor, testli CRUD | verified |
| M1.3 | Harcama giriş formu (tek sayfa web UI) | tarayıcıdan harcama eklenebiliyor | verified |
| M1.4 | TÜİK/EVDS TÜFE ingestion job | son 24 ay TÜFE DB'de, idempotent | tested |
| M1.5 | Kişisel endeks hesap motoru (Laspeyres) | birim testli, elle doğrulanmış örnek | planned |
| M1.6 | Kıyas ekranı: "senin %Y vs resmi %X" | tek ekranda iki sayı | planned |
| M1.7 | Deploy (ücretsiz tier: Fly.io/Render + Neon/Supabase PG) | telefondan URL ile erişilebiliyor | planned |

**M1 Done tanımı:** Umut 14 gün kendi harcamasını girmiş ve app ilk kişisel
enflasyon sayısını göstermiş durumda; deploy canlı; CI yeşil.

### M2 — Veri derinliği (taslak)

- Kategori bazlı alt endeksler (gıda/ulaşım/eğlence)
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
| 2026-08-18 | TÜFE kaynağı: TCMB EVDS API, seri `TP.FG.J0` (2003=100, aylık) | Resmi kaynak, ücretsiz, JSON; TÜİK sitesinde stabil API yok |
| 2026-08-18 | Ingest'te fetch/parse ayrımı; CI'da canlı API çağrısı yok (MockTransport) | Parser ağsız test edilir; dış servise bağımlı test flaky + secret riski |
| 2026-08-18 | EVDS anahtarı `EVDS_API_KEY` env'den, HTTP `key` header'ında | Secret koda/repoya girmez; EVDS anahtarı query'de değil header'da ister |
