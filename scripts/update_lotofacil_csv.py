import csv
import os
import time
import requests

API_BASE = "https://api.guidi.dev.br/loteria/lotofacil"
CSV_PATH = os.path.join("data", "lotofacil.csv")

def get_json(url: str) -> dict:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def to_iso_date(date_str: str) -> str:
    if not date_str:
        return ""
    if "-" in date_str and len(date_str) >= 10:
        return date_str[:10]
    if "/" in date_str:
        d, m, y = date_str.split("/")[:3]
        return f"{y.zfill(4)}-{m.zfill(2)}-{d.zfill(2)}"
    return date_str

def extract_numbers(j: dict) -> list[int]:
    for key in ["dezenas", "listaDezenas", "numeros", "resultadoOrdenado", "listaDezenasSorteadas"]:
        if key in j and isinstance(j[key], list) and len(j[key]) >= 15:
            nums = [int(x) for x in j[key][:15]]
            nums.sort()
            return nums
    raise ValueError("Não achei as 15 dezenas")

def get_contest_number(j: dict) -> int:
    for key in ["concurso", "numero", "numeroConcurso"]:
        if key in j:
            return int(j[key])
    raise ValueError("Não achei o número do concurso")

def get_contest_date(j: dict) -> str:
    for key in ["data", "dataApuracao", "dataSorteio"]:
        if key in j:
            return to_iso_date(j[key])
    return ""

def read_last_contest(path: str) -> int:
    if not os.path.exists(path):
        return 0
    last = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            try:
                last = max(last, int(row[0]))
            except:
                pass
    return last

def append_rows(path: str, rows: list[list]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.exists(path)

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow([
                "concurso","data",
                "d1","d2","d3","d4","d5","d6","d7","d8","d9",
                "d10","d11","d12","d13","d14","d15"
            ])
        for r in rows:
            writer.writerow(r)

def main():
    ultimo = get_json(f"{API_BASE}/ultimo")
    last_api = get_contest_number(ultimo)
    last_csv = read_last_contest(CSV_PATH)

    start = 1 if last_csv < 50 else last_csv + 1
    if start > last_api:
        print("CSV já está atualizado")
        return

    rows = []
    for n in range(start, last_api + 1):
        j = get_json(f"{API_BASE}/{n}")
        concurso = get_contest_number(j)
        data = get_contest_date(j)
        dezenas = extract_numbers(j)
        rows.append([concurso, data] + dezenas)

        time.sleep(0.1)

        if len(rows) >= 200:
            append_rows(CSV_PATH, rows)
            rows = []

    if rows:
        append_rows(CSV_PATH, rows)

    print(f"CSV atualizado até o concurso {last_api}")

if __name__ == "__main__":
    main()
