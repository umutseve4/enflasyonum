# Enflasyonumdan ne haber?

**Kişisel enflasyon endeksi.** TÜİK "%X" der; senin sepetin farklıdır. Bu uygulama
kendi harcamalarını girip **kendi enflasyon oranını** hesaplamanı ve resmi
endekslerle (TÜİK TÜFE) kıyaslamanı sağlar.

> Repo slug'ı `enflasyonum` (kısa, URL/import dostu); uygulama adı
> **"Enflasyonumdan ne haber?"**

## Canlı demo

🔗 **Demo:** https://enflasyonum-7gcn.onrender.com — [/health](https://enflasyonum-7gcn.onrender.com/health) · [/card.svg](https://enflasyonum-7gcn.onrender.com/card.svg) · [/history.svg](https://enflasyonum-7gcn.onrender.com/history.svg) · [/export.csv](https://enflasyonum-7gcn.onrender.com/export.csv)

> Not: Render free tier 15 dk hareketsizlikte uyur; ilk istek ~30-60 sn sürebilir.
> Canlı servis her hafta [verify-live](.github/workflows/verify-live.yml) workflow'u ile otomatik doğrulanır.

## Problem

Resmi enflasyon bir ortalama sepetin ölçümüdür; kimsenin sepeti ortalama değildir.
Kişisel sepet ağırlıklarıyla hesaplanan bireysel endeks, "benim enflasyonum kaç?"
sorusuna doğrulanabilir bir cevap verir.

## Özellikler

- **Harcama girişi:** tutar + kategori + tarih (web form)
- **Kişisel endeks:** kişisel sepet ağırlıklı Laspeyres endeksi, **13 ECOICOP
  alt endeksi** üzerinde ayrıştırılmış hesap
- **TÜİK TÜFE kıyası:** tek ekran, tek sayı — "senin enflasyonun %Y, resmi %X"
  (canlı örnek: kişisel %23.05 vs resmi %31.75)
- **Özet kartı:** `/card.svg` — paylaşılabilir SVG özet kartı
- **Geçmiş grafiği:** `/history.svg`
- **CSV dışa aktarma:** `/export.csv` (CSV-injection korumalı)
- **M1 kullanım ilerlemesi:** `/usage-progress` yalnız `distinct_days`, `target_days`,
  `remaining_days` ve `complete` aggregate alanlarını döndürür; tarih, tutar,
  kategori, açıklama veya harcama satırı yayımlamaz
- **TÜİK açıklama günü bildirimi:** yeni TÜFE bülteni yayımlandığında GitHub
  Actions otomatik issue açar (idempotent, `tufe-bildirim` etiketi)
- **Otomatik günlük veri çekimi:** TCMB EVDS üzerinden resmi TÜFE serisi
  (`TP.TUKFIY2025.GENEL`, 2025=100 bazlı)

## Kurulum (geliştirme)

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn enflasyonum.main:app --reload
# http://127.0.0.1:8000/health
```

Testler ve lint:

```bash
pytest
ruff check src tests
```

## Mimari

```
TÜİK/EVDS API ──▶ günlük ingest (GitHub Actions) ──▶ PostgreSQL ◀── kullanıcı harcama girişi (FastAPI)
                                                        │
                                                        ▼
                                     endeks hesap motoru (Laspeyres, 13 ECOICOP)
                                                        │
                                                        ▼
                  API ──▶ web UI · /card.svg · /history.svg · /export.csv · /usage-progress
```

## Durum (dürüst)

Kod sürümü **v0.7.1** — canlı sürüm ve milestone doğruluğu için [ROADMAP.md](ROADMAP.md).
`/usage-progress`, M1'in 14 gerçek kullanım günü kapısını yalnız ölçer; milestone'u
otomatik kapatmaz ve private sayaç sonucu kamuya açık belgelere taşınmaz.

| Aşama | Durum |
|---|---|
| M1 — Dikey dilim: giriş + endeks + TÜFE kıyası + canlı deploy | 🟡 teknik akış canlıda doğrulandı; 14 günlük gerçek kullanım Done kapısı henüz kapanmadı |
| M2 — 13 ECOICOP alt endeksi + özet kartı + haftalık canlı doğrulama | ✅ canlıda doğrulandı |
| M3.1 — CSV dışa aktarma | ✅ canlıda doğrulandı |
| M3.2 — TÜİK açıklama günü bildirimi | ✅ gerçek TÜFE açıklamasında issue #16 ile canlıda doğrulandı |
| M4.1 — Ana sayfa görsel yenilemesi | ✅ PR #15 ve canlı v0.7.0 kullanıcı onayıyla doğrulandı |

Kapsam DIŞI (şimdilik): OCR/fiş okuma, mobil uygulama mağazası, çoklu kullanıcı
yönetim paneli, tahmin/ML.

## Teknoloji

Python 3.11+, FastAPI, PostgreSQL, pytest, ruff, GitHub Actions CI
(test + lint + canlı smoke).

## Lisans

MIT — bkz. [LICENSE](LICENSE).
