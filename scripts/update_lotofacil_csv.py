import csv
import os
import time
import requests

API_BASE = "https://api.guidi.dev.br/loteria/lotofacil"
CSV_PATH = os.path.join("data", "lotofacil.csv")

def get_json(url: str, retries=5):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"Erro na API ({url}) tentativa {i+1}/{retries}: {e}")
            time.sleep(2)
    return None

def to_iso_date(date_str: str) -> str:
    if not date_str:
        return ""
    if "-" in date_str:
        return date_str[:10]
    if "/" in date_str:
        d, m, y = date_str.split("/")[:3]
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return date_str

def extract_numbers(j: dict):
    for key in ["dezenas", "listaDezenas", "numeros", "resultadoOrdenado", "listaDezenasSorteadas"]:
        if key in j and isinstance(j[key], list):
            nums = sorted(int(x) for x in j[key][:15])
            return nums
    return None

def get_contest_number(j: dict):
    for key in ["concurso", "numero", "numeroConcurso"]:
        if key in j:
            return int(j[key])
    return None

def get_contest_date(j: dict):
    for key in ["data", "dataApuracao", "dataSorteio"]:
        if key in j:
            return to_iso_date(j[key])
    return ""

def read_last_contest(path: str):
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

def append_rows(path: str, rows):
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
        writer.writerows(rows)

def main():
    ultimo = get_json(f"{API_BASE}/ultimo")
    if not ultimo:
        print("Erro ao buscar último concurso")
        return

    last_api = get_contest_number(ultimo)
    last_csv = read_last_contest(CSV_PATH)

    print(f"Último concurso API: {last_api}")
    print(f"Último concurso CSV: {last_csv}")

    start = last_csv + 1

    if start > last_api:
        print("CSV já está atualizado")
        return

    rows = []
    contador = 0

    for n in range(start, last_api + 1):
        j = get_json(f"{API_BASE}/{n}")
        if not j:
            print(f"Pulando concurso {n} (erro API)")
            continue

        concurso = get_contest_number(j)
        dezenas = extract_numbers(j)

        if not concurso or not dezenas:
            print(f"Concurso inválido: {n}")
            continue

        data = get_contest_date(j)
        rows.append([concurso, data] + dezenas)
        contador += 1

        # salva a cada 50 concursos (evita timeout)
        if contador % 50 == 0:
            append_rows(CSV_PATH, rows)
            print(f"Salvo até concurso {concurso}")
            rows = []

        time.sleep(0.05)  # mais rápido

    if rows:
        append_rows(CSV_PATH, rows)

    print(f"CSV atualizado até o concurso {last_api}")

if __name__ == "__main__":
    main()
