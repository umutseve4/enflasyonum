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

PR, exact head SHA, hosted CI run/job kimlikleri, merge SHA ve mümkünse privacy-safe canlı kontrat doğrulaması tamamlandığında buraya ve issue #25'e eklenecektir.
