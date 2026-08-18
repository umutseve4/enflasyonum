"""M2.1 seri kataloğu testleri: ECOICOP kodları ve kategori eşlemesi."""

from enflasyonum import series


def test_all_series_has_headline_plus_13_divisions():
    assert len(series.ALL_SERIES) == 14
    assert series.ALL_SERIES[0] == "TP.TUKFIY2025.GENEL"
    assert series.division_series("01") in series.ALL_SERIES
    assert series.division_series("13") in series.ALL_SERIES


def test_division_series_format():
    assert series.division_series("07") == "TP.TUKFIY2025.07"


def test_json_key_replaces_dots():
    assert series.json_key("TP.TUKFIY2025.01") == "TP_TUKFIY2025_01"


def test_category_to_series_known_names():
    assert series.category_to_series("gıda") == "TP.TUKFIY2025.01"
    assert series.category_to_series("kozmetik") == "TP.TUKFIY2025.13"
    assert series.category_to_series("ulaşım") == "TP.TUKFIY2025.07"
    assert series.category_to_series("kira") == "TP.TUKFIY2025.04"


def test_category_to_series_normalizes_whitespace():
    # Not: büyük İ -> lower() Unicode'da combining dot üretir (İ != i sorunu);
    # uygulama katmanı (main.py) kategoriyi zaten kayıtta lower'lıyor.
    assert series.category_to_series("  kozmetik  ") == "TP.TUKFIY2025.13"


def test_category_to_series_ascii_variant():
    assert series.category_to_series("gida") == "TP.TUKFIY2025.01"


def test_category_to_series_unknown_returns_none():
    assert series.category_to_series("zımbırtı") is None
