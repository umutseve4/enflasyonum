# DEPLOY — Render (web) + Neon (PostgreSQL) + Actions (cron)

> Mimari: Render free web servisi FastAPI'yi koşar; Neon free PostgreSQL veriyi
> tutar; GitHub Actions her gün 07:30 UTC'de EVDS'den TÜFE çeker (idempotent).
> Render free instance ~15 dk hareketsizlikte uyur; ilk istek ~30-60 sn sürer.
> Bu, kişisel kullanım için kabul edilebilir bir M1 ödünleşimidir.

## Neon URL formatı — KRİTİK

Neon'un verdiği URL `postgresql://...` ile başlar. Bu projede sürücü psycopg3
olduğu için başı **`postgresql+psycopg://`** yapılmalıdır (gerisi aynen kalır):

```
postgresql+psycopg://KULLANICI:SIFRE@HOST/neondb?sslmode=require
```

## Umut'un tık listesi

### 1. Neon (veritabanı)
1. https://neon.tech → GitHub ile giriş → yeni proje: `enflasyonum` (bölge: EU).
2. Dashboard'daki **Connection string**'i kopyala; başını `postgresql+psycopg://` yap.

### 2. Render (web)
1. https://render.com → GitHub ile giriş → **New + → Blueprint** → `umutseve4/enflasyonum` repo'sunu seç (render.yaml otomatik okunur).
2. `DATABASE_URL` sorulduğunda 1. adımdaki (düzeltilmiş) URL'yi yapıştır → **Apply**.
3. Deploy bitince verilen `https://enflasyonum-XXXX.onrender.com/health` adresini aç — `{"status":"ok"}` görmelisin.

### 3. GitHub secret (günlük ingest için)
1. Repo → **Settings → Secrets and variables → Actions → New repository secret**.
2. Ad: `LIVE_DATABASE_URL`, değer: aynı düzeltilmiş Neon URL'si → kaydet.
3. **Actions → daily-ingest → Run workflow** ile bir kez elle tetikle; yeşil bitince canlı DB'de 24 ay TÜFE var demektir.

## Doğrulama (M1.5+M1.6 → verified)

1. Uygulama URL'sini aç, bir harcama gir.
2. Üstte iki kart göreceksin: senin enflasyonun ve resmi TÜFE (M1'de eşit — ekranda açıklanıyor).
3. Bu ekran görüntüsünü paylaş → durum `verified`e çekilir.

## Güvenlik notları

- `DATABASE_URL` ve `EVDS_API_KEY` yalnızca Render env + GitHub Secrets'ta durur; repoya asla yazılmaz.
- Neon `sslmode=require` ile bağlanır.
