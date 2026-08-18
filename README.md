# enflasyonum

**Kişisel enflasyon endeksi.** TÜİK "%X" der; senin sepetin farklıdır. Bu uygulama
kendi harcamalarını girip **kendi enflasyon oranını** hesaplamanı ve resmi
endekslerle (TÜİK TÜFE) kıyaslamanı sağlar.

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
