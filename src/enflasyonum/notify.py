"""M3.2: TÜİK açıklama günü bildirimi — GitHub issue katmanı.

daily-ingest workflow'u ingest çıktısını ingest.log'a yazar; bu modül
log'daki level-triggered marker'ı (HEADLINE_LATEST_PERIOD, koşullu
HEADLINE_MOM_PCT) okur ve aynı dönem için issue yoksa `gh issue create`
ile açar.

Kurallar (karar kaydı: ROADMAP.md):
- İdempotentlik: sabit `tufe-bildirim` label'ı + tam başlık öneki
  karşılaştırması (`gh issue list --json title`, serbest metin arama
  değil). Aynı dönem için ikinci issue açılmaz; geçici bir create
  hatası ertesi günkü koşuda otomatik yeniden denenir (level-trigger).
- Kanıt hijyeni: issue gövdesine KİŞİSEL enflasyon sayısı ve kişisel
  veri gösteren hiçbir uygulama URL'si yazılmaz — yalnız resmi veri.
- gh çağrıları `runner` parametresiyle enjekte edilebilir (test için);
  subprocess argüman listesiyle, shell=False çalışır.

Kullanım (workflow):
    GH_TOKEN=... GH_REPO=owner/repo python -m enflasyonum.notify ingest.log
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

LABEL = "tufe-bildirim"
TITLE_PREFIX = "\U0001f4e2 TÜFE açıklandı: "
PERIOD_RE = re.compile(r"^HEADLINE_LATEST_PERIOD=(\d{4}-\d{2})$", re.MULTILINE)
PCT_RE = re.compile(r"^HEADLINE_MOM_PCT=(-?\d+\.\d{2})$", re.MULTILINE)


def run_gh(args: list[str]) -> subprocess.CompletedProcess:
    """gh CLI'yi argüman listesiyle çalıştır (shell=False, check=False)."""
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )


def parse_markers(text: str) -> tuple[str | None, str | None]:
    """ingest.log'dan (dönem, aylık %) çıkar; marker yoksa (None, None)."""
    period_match = PERIOD_RE.search(text)
    if period_match is None:
        return None, None
    pct_match = PCT_RE.search(text)
    return period_match.group(1), pct_match.group(1) if pct_match else None


def issue_title(period: str, pct: str | None) -> str:
    base = f"{TITLE_PREFIX}{period}"
    if pct is None:
        return base
    return f"{base} — resmi aylık %{pct}"


def issue_body(period: str, pct: str | None) -> str:
    """Yalnız resmi veri; kişisel veri gösteren URL/sayı YOK (kanıt hijyeni)."""
    lines = [f"TÜİK {period} dönemi TÜFE endeksi yayımlandı (kaynak: TCMB EVDS)."]
    if pct is not None:
        lines.append(f"Resmi aylık değişim: %{pct}")
    else:
        lines.append("Aylık değişim hesaplanamadı (önceki ay verisi yok).")
    lines.append(
        "Kişisel karşılaştırma için kendi enflasyon ekranını aç "
        "(bağlantı bilinçli olarak eklenmedi — public kanala kişisel veri yok)."
    )
    return "\n\n".join(lines)


def issue_exists(period: str, runner=run_gh) -> bool:
    """Aynı dönem için tufe-bildirim label'lı issue var mı? (tam önek eşleşmesi)"""
    res = runner(
        [
            "issue", "list", "--state", "all", "--label", LABEL,
            "--limit", "1000", "--json", "title",
        ]
    )
    if res.returncode != 0:
        raise RuntimeError(f"gh issue list basarisiz: {res.stderr.strip()}")
    titles = [item["title"] for item in json.loads(res.stdout or "[]")]
    prefix = f"{TITLE_PREFIX}{period}"
    return any(t.startswith(prefix) for t in titles)


def main(argv: list[str], runner=run_gh) -> int:
    print("===== OTOMATIK KONTROL =====")
    if not argv:
        print("sonuc: FAIL (kullanim: python -m enflasyonum.notify ingest.log)")
        return 1
    log_path = Path(argv[0])
    if not log_path.exists():
        print(f"log yok ({log_path}) — ingest kosmadi, bildirim atlandi")
        print("sonuc: PASS")
        return 0
    period, pct = parse_markers(log_path.read_text(encoding="utf-8"))
    if period is None:
        print("marker yok — bildirim atlandi")
        print("sonuc: PASS")
        return 0
    try:
        if issue_exists(period, runner=runner):
            print(f"issue zaten var: {period} — atlandi (idempotent)")
            print("sonuc: PASS")
            return 0
        label_res = runner(
            [
                "label", "create", LABEL, "--force",
                "--color", "1d76db",
                "--description", "TÜFE açıklama bildirimi (otomatik)",
            ]
        )
        if label_res.returncode != 0:
            print(f"sonuc: FAIL (label create: {label_res.stderr.strip()})")
            return 1
        create_res = runner(
            [
                "issue", "create",
                "--title", issue_title(period, pct),
                "--body", issue_body(period, pct),
                "--label", LABEL,
            ]
        )
        if create_res.returncode != 0:
            print(f"sonuc: FAIL (issue create: {create_res.stderr.strip()})")
            return 1
    except RuntimeError as exc:
        print(f"sonuc: FAIL ({exc})")
        return 1
    print(f"issue acildi: {period}")
    print("sonuc: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
