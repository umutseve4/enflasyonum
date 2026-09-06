<h1 align="center">Enflasyonumdan ne haber?</h1>

<p align="center">
  TÜİK bir ortalama sepeti ölçer; kimsenin sepeti ortalama değildir.<br>
  Kendi harcamalarını gir, kendi enflasyonunu hesapla, resmi oranla yan yana gör.<br>
  <b>Canlı örnek: kişisel %23.05 · resmi %31.75</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/ECOICOP%20alt%20endeksi-13-FF4D4F?style=flat-square" alt="13 ECOICOP alt endeksi">
  <img src="https://img.shields.io/badge/public%20u%C3%A7-2-FF4D4F?style=flat-square" alt="2 public uç">
  <img src="https://img.shields.io/badge/s%C3%BCr%C3%BCm-v0.7.1-FF4D4F?style=flat-square" alt="v0.7.1">
</p>

<p align="center">
  <b><a href="https://enflasyonum-7gcn.onrender.com/health">▶ Canlı servis — /health</a></b><br>
  <sub>Public uçlar yalnızca <a href="https://enflasyonum-7gcn.onrender.com/health">/health</a> ve <a href="https://enflasyonum-7gcn.onrender.com/usage-progress">/usage-progress</a>; geri kalan her şey owner-private.</sub>
</p>

---

## 30 saniyede ne oluyor?

Tutar + kategori + tarih girersin. Uygulama kişisel sepet ağırlıklarınla bir
**Laspeyres endeksi** hesaplar, bunu **13 ECOICOP alt endeksine** ayrıştırır ve
resmi TÜİK TÜFE serisiyle (`TP.TUKFIY2025.GENEL`, 2025=100 bazlı, TCMB EVDS
üzerinden günlük çekilir) tek ekranda karşılaştırır.

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn enflasyonum.main:app --reload
# http://127.0.0.1:8000/health
```

```bash
pytest
ruff check src tests
```

## Ne üretir

| Uç | Ne verir |
|---|---|
| web form | tutar + kategori + tarih ile harcama girişi |
| kişisel endeks | kişisel sepet ağırlıklı Laspeyres, 13 ECOICOP alt endeksinde ayrıştırılmış |
| TÜİK kıyası | tek ekran, tek sayı — "senin enflasyonun %Y, resmi %X" |
| `/card.svg` | paylaşılabilir SVG özet kartı |
| `/history.svg` | geçmiş grafiği |
| `/export.csv` | CSV dışa aktarma (CSV-injection korumalı) |
| `/usage-progress` | yalnız `distinct_days`, `target_days`, `remaining_days`, `complete` |

**TÜİK açıklama günü bildirimi:** yeni TÜFE bülteni yayımlandığında GitHub Actions
otomatik issue açar (idempotent, `tufe-bildirim` etiketi).

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

Kod sürümü **v0.7.1** — canlı sürüm ve milestone doğruluğu için
[ROADMAP.md](ROADMAP.md).

| Aşama | Durum |
|---|---|
| M1 — Dikey dilim: giriş + endeks + TÜFE kıyası + canlı deploy | 🟡 teknik akış canlıda doğrulandı; 14 günlük gerçek kullanım Done kapısı henüz kapanmadı |
| M2 — 13 ECOICOP alt endeksi + özet kartı + haftalık canlı doğrulama | ✅ canlıda doğrulandı |
| M3.1 — CSV dışa aktarma | ✅ canlıda doğrulandı |
| M3.2 — TÜİK açıklama günü bildirimi | ✅ gerçek TÜFE açıklamasında issue #16 ile canlıda doğrulandı |
| M4.1 — Ana sayfa görsel yenilemesi | ✅ PR #15 ve canlı v0.7.0 kullanıcı onayıyla doğrulandı |

`/usage-progress`, M1'in 14 gerçek kullanım günü kapısını yalnız ölçer;
milestone'u otomatik kapatmaz ve private sayaç sonucu kamuya açık belgelere
taşınmaz.

## Sınırlar

- **Gizlilik fail-closed'dur.** Public allowlist yalnızca `GET/HEAD /health` ve `GET/HEAD /usage-progress`. Diğer tüm uçlar owner-private: `/`, `/card.svg`, `/history.svg`, `/export.csv`, `POST /expenses`, `/docs`, `/redoc`, `/openapi.json` ve gelecekte eklenecek diğer yollar/metotlar. Deploy öncesi `ENFLASYONUM_OWNER_TOKEN` zorunludur; boş/missing ise private istekler **503** döner. Kullanıcı adı varsayılanı `owner`, gerekirse `ENFLASYONUM_OWNER_USERNAME` ile değiştirilir.
- **Demo uyur.** Render free tier 15 dk hareketsizlikte uyur; ilk istek ~30–60 sn sürebilir. Canlı servis her hafta [verify-live](.github/workflows/verify-live.yml) workflow'u ile otomatik doğrulanır.
- **Kapsam dışı (şimdilik):** OCR/fiş okuma, mobil uygulama mağazası, çoklu kullanıcı yönetim paneli, tahmin/ML.
- Repo slug'ı `enflasyonum` (kısa, URL/import dostu); uygulama adı **"Enflasyonumdan ne haber?"**

Teknoloji: Python 3.11+, FastAPI, PostgreSQL, pytest, ruff, GitHub Actions CI
(test + lint + canlı smoke).

---

MIT — bkz. [LICENSE](LICENSE).
