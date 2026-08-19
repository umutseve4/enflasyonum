"""M3.2 notify.py testleri — idempotentlik, hata yolları, kanıt hijyeni."""

import json

from enflasyonum import notify


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunner:
    """gh çağrılarını kaydeder; (komut, alt komut) çiftine göre yanıt döner."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def __call__(self, args):
        self.calls.append(args)
        return self.responses.get(tuple(args[:2]), FakeResult())


def test_parse_markers_full():
    text = "sonuc: PASS\nHEADLINE_LATEST_PERIOD=2026-07\nHEADLINE_MOM_PCT=2.06\n"
    assert notify.parse_markers(text) == ("2026-07", "2.06")


def test_parse_markers_period_only():
    text = "sonuc: PASS\nHEADLINE_LATEST_PERIOD=2026-07\n"
    assert notify.parse_markers(text) == ("2026-07", None)


def test_parse_markers_absent():
    assert notify.parse_markers("sonuc: FAIL\n") == (None, None)


def test_parse_markers_negative_pct():
    text = "HEADLINE_LATEST_PERIOD=2026-07\nHEADLINE_MOM_PCT=-0.35\n"
    assert notify.parse_markers(text) == ("2026-07", "-0.35")


def test_issue_title_with_and_without_pct():
    assert notify.issue_title("2026-07", "2.06") == (
        "\U0001f4e2 TÜFE açıklandı: 2026-07 — resmi aylık %2.06"
    )
    assert notify.issue_title("2026-07", None) == "\U0001f4e2 TÜFE açıklandı: 2026-07"


def test_issue_body_has_no_urls():
    """Kanıt hijyeni: public issue gövdesinde hiçbir URL olamaz (QA bulgu 4)."""
    for pct in ("2.06", None):
        body = notify.issue_body("2026-07", pct)
        assert "http" not in body
        assert "://" not in body


def test_issue_body_pct_none_explains():
    body = notify.issue_body("2026-07", None)
    assert "Aylık değişim hesaplanamadı" in body


def test_main_missing_log_silent_pass(tmp_path, capsys):
    runner = FakeRunner()
    rc = notify.main([str(tmp_path / "yok.log")], runner=runner)
    assert rc == 0
    assert runner.calls == []  # gh hiç çağrılmadı
    assert "sonuc: PASS" in capsys.readouterr().out


def test_main_no_marker_silent_pass(tmp_path, capsys):
    log = tmp_path / "ingest.log"
    log.write_text("sonuc: FAIL\n", encoding="utf-8")
    runner = FakeRunner()
    rc = notify.main([str(log)], runner=runner)
    assert rc == 0
    assert runner.calls == []
    assert "sonuc: PASS" in capsys.readouterr().out


def test_main_no_args_fails():
    assert notify.main([], runner=FakeRunner()) == 1


def _log_with_marker(tmp_path, pct="2.06"):
    log = tmp_path / "ingest.log"
    lines = ["sonuc: PASS", "HEADLINE_LATEST_PERIOD=2026-07"]
    if pct is not None:
        lines.append(f"HEADLINE_MOM_PCT={pct}")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log


def test_main_existing_issue_skips_create(tmp_path, capsys):
    """İdempotentlik: aynı dönem issue'su varsa create ÇAĞRILMAZ (QA bulgu 5)."""
    existing = json.dumps(
        [{"title": "\U0001f4e2 TÜFE açıklandı: 2026-07 — resmi aylık %2.06"}]
    )
    runner = FakeRunner({("issue", "list"): FakeResult(stdout=existing)})
    rc = notify.main([str(_log_with_marker(tmp_path))], runner=runner)
    assert rc == 0
    assert [c[:2] for c in runner.calls] == [["issue", "list"]]
    assert "idempotent" in capsys.readouterr().out


def test_main_other_period_issue_does_not_block(tmp_path):
    """Başka dönemin issue'su yeni dönemi bastırmamalı (tam önek eşleşmesi)."""
    existing = json.dumps([{"title": "\U0001f4e2 TÜFE açıklandı: 2026-06"}])
    runner = FakeRunner({("issue", "list"): FakeResult(stdout=existing)})
    rc = notify.main([str(_log_with_marker(tmp_path))], runner=runner)
    assert rc == 0
    assert ["issue", "create"] in [c[:2] for c in runner.calls]


def test_main_creates_issue_with_label_and_title(tmp_path, capsys):
    runner = FakeRunner({("issue", "list"): FakeResult(stdout="[]")})
    rc = notify.main([str(_log_with_marker(tmp_path))], runner=runner)
    assert rc == 0
    kinds = [c[:2] for c in runner.calls]
    assert kinds == [["issue", "list"], ["label", "create"], ["issue", "create"]]
    create = runner.calls[-1]
    title = create[create.index("--title") + 1]
    body = create[create.index("--body") + 1]
    label = create[create.index("--label") + 1]
    assert title == "\U0001f4e2 TÜFE açıklandı: 2026-07 — resmi aylık %2.06"
    assert label == notify.LABEL
    assert "http" not in body  # kanıt hijyeni
    assert "issue acildi: 2026-07" in capsys.readouterr().out


def test_main_create_failure_returns_1(tmp_path, capsys):
    """gh create hatası kırmızı biter → level-trigger ertesi gün retry eder."""
    runner = FakeRunner(
        {
            ("issue", "list"): FakeResult(stdout="[]"),
            ("issue", "create"): FakeResult(returncode=1, stderr="boom"),
        }
    )
    rc = notify.main([str(_log_with_marker(tmp_path))], runner=runner)
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out


def test_main_list_failure_returns_1(tmp_path):
    runner = FakeRunner({("issue", "list"): FakeResult(returncode=1, stderr="401")})
    assert notify.main([str(_log_with_marker(tmp_path))], runner=runner) == 1


def test_main_label_failure_returns_1(tmp_path):
    runner = FakeRunner(
        {
            ("issue", "list"): FakeResult(stdout="[]"),
            ("label", "create"): FakeResult(returncode=1, stderr="denied"),
        }
    )
    assert notify.main([str(_log_with_marker(tmp_path))], runner=runner) == 1
