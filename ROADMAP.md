# ROADMAP — tek doğruluk kaynağı

> Her oturuma buradan başlanır. "Şu an neredeyiz?" sorusunun cevabı bu dosyadır.
> Durum etiketleri: `planned` → `implemented` → `tested` → `verified` → `deployed`.

## ŞU AN NEREDEYİZ

**Aşama:** M1 başlangıcı — repo iskeleti kuruldu (2026-08-18).
**Sıradaki tek iş:** M1.1 — FastAPI iskeleti + `/health` endpoint + CI yeşil.

## Milestone'lar

### M1 — Dikey dilim (hedef: 2 hafta, bitiş ~2026-09-01)

Tek akış: harcama gir → ay sonunda kişisel endeks + TÜİK kıyası tek ekranda.

| # | İş | Kabul kriteri | Durum |
|---|---|---|---|
| M1.1 | FastAPI iskeleti + `/health` + CI (pytest+ruff) | CI yeşil, endpoint 200 döner | planned |
| M1.2 | PostgreSQL şeması: `expenses`, `categories`, `official_cpi` | migration koşuyor, testli CRUD | planned |
| M1.3 | Harcama giriş formu (tek sayfa web UI) | tarayıcıdan harcama eklenebiliyor | planned |
| M1.4 | TÜİK/EVDS TÜFE ingestion job | son 24 ay TÜFE DB'de, idempotent | planned |
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
