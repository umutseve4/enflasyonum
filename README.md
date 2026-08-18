# Enflasyonumdan ne haber?

**Kişisel enflasyon endeksi.** TÜİK "%X" der; senin sepetin farklıdır. Bu uygulama
kendi harcamalarını girip **kendi enflasyon oranını** hesaplamanı ve resmi
endekslerle (TÜİK TÜFE) kıyaslamanı sağlar.

> Repo slug'ı `enflasyonum` (kısa, URL/import dostu); uygulama adı
> **"Enflasyonumdan ne haber?"**
>
> Durum: 🚧 M1 (dikey dilim) geliştirme aşamasında — henüz çalışan sürüm yok.
> Güncel durum için [ROADMAP.md](ROADMAP.md).

## Problem

Resmi enflasyon bir ortalama sepetin ölçümüdür; kimsenin sepeti ortalama değildir.
Kişisel sepet ağırlıklarıyla hesaplanan bireysel endeks, "benim enflasyonum kaç?"
sorusuna doğrulanabilir bir cevap verir.

## Kapsam (M1 dikey dilim)

- Harcama girişi: tutar + kategori + tarih (web form)
- Aylık kişisel endeks: kişisel sepet ağırlıklı fiyat değişimi (Laspeyres yaklaşımı)
- TÜİK TÜFE ile kıyas: tek ekran, tek sayı — "senin enflasyonun %Y, resmi %X"

Kapsam DIŞI (şimdilik): OCR/fiş okuma, mobil uygulama mağazası, çoklu kullanıcı
yönetim paneli, tahmin/ML.

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

## Mimari (planlanan)

```
TÜİK/EVDS API ──▶ ingestion job ──▶ PostgreSQL ◀── kullanıcı harcama girişi (FastAPI)
                                        │
                                        ▼
                              endeks hesap motoru ──▶ API ──▶ web UI
```

## Teknoloji

Python 3.11+, FastAPI, PostgreSQL, pytest, ruff, GitHub Actions CI.

## Lisans

MIT — bkz. [LICENSE](LICENSE).
