import os

import httpx

BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
HEADERS = {"key": os.environ["EVDS_API_KEY"]}


def get(url):
    response = httpx.get(url, headers=HEADERS, timeout=30)
    return response.status_code, response


def try_json(label, url):
    try:
        code, response = get(url)
        print(f"[{label}] HTTP {code} url={url}")
        if code == 200:
            try:
                return response.json()
            except Exception as error:
                print(f"[{label}] JSON parse hatasi: {error}; ilk 200 kr: {response.text[:200]}")
        else:
            print(f"[{label}] govde ilk 200 kr: {response.text[:200]}")
    except Exception as error:
        print(f"[{label}] istek hatasi: {error}")
    return None


print("== 1) datagroups endpoint denemeleri ==")
groups = None
for label, url in [
    ("dg-a", BASE + "datagroups?mode=0&type=json"),
    ("dg-b", BASE + "datagroups/mode=0&type=json"),
    ("dg-c", BASE + "datagroups?mode=2&code=bie_tukfiy&type=json"),
]:
    data = try_json(label, url)
    if isinstance(data, list) and data:
        groups = data
        print(f"[{label}] OK — {len(data)} grup")
        break

candidates = []
if groups:
    print("\n== 2) TUFE/2025 gecen gruplar ==")
    for group in groups:
        name = str(group.get("DATAGROUP_NAME") or group.get("DATAGROUP_NAME_ENG") or "")
        code = str(group.get("DATAGROUP_CODE") or "")
        blob = (name + " " + code).lower()
        if any(key in blob for key in ("tuketici", "tüketici", "tufe", "tüfe", "2025")):
            candidates.append(code)
            print(f"GRUP: {code} | {name}")

if not candidates:
    candidates = ["bie_tukfiy", "bie_tukfiy2025", "bie_tufe2025", "bie_oktug2025"]
    print(f"(metadata yok — varsayilan adaylar: {candidates})")

print("\n== 3) serieList denemeleri ==")
for group_code in candidates:
    for label, url in [
        (f"sl-a-{group_code}", BASE + f"serieList?type=json&code={group_code}"),
        (f"sl-b-{group_code}", BASE + f"serieList/type=json&code={group_code}"),
    ]:
        data = try_json(label, url)
        if isinstance(data, list) and data:
            for series in data:
                series_code = str(series.get("SERIE_CODE") or "")
                series_name = str(series.get("SERIE_NAME") or "")
                print(f"SERI: {series_code} | {series_name} | grup={group_code}")
            break

print("\n== 4) aday seri kodlarini canli probe et (2026 verisi var mi?) ==")
probes = ["TP.FG.J0", "TP.FG.J02", "TP.FG25.J0", "TP.TUFE2025.J0", "TP.FG2025.J0"]
hits = []
for series_code in probes:
    url = (
        BASE
        + f"series={series_code}"
        + "&startDate=01-01-2026&endDate=01-08-2026&type=json"
    )
    try:
        code, response = get(url)
        count = 0
        last = ""
        if code == 200:
            try:
                items = response.json().get("items", [])
                key = series_code.replace(".", "_")
                values = [
                    (item.get("Tarih"), item.get(key))
                    for item in items
                    if item.get(key) is not None
                ]
                count = len(values)
                last = str(values[-1]) if values else ""
            except Exception as error:
                last = f"parse hatasi: {error}"
        print(f"PROBE: {series_code} -> HTTP {code}, dolu deger: {count}, son: {last}")
        if count > 0 and series_code != "TP.FG.J0":
            hits.append(series_code)
    except Exception as error:
        print(f"PROBE: {series_code} -> istek hatasi: {error}")

print("\n===== OTOMATIK KONTROL =====")
print(f"yeni seri adayi bulunan: {hits if hits else 'YOK'}")
print("sonuc: PASS" if hits else "sonuc: INCONCLUSIVE")
