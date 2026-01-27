import csv
import requests
from pathlib import Path

OUTPUT_FILE = Path("data/lotofacil.csv")

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0"
}

BASE_URL = "https://loteriascaixa-api.herokuapp.com/api/lotofacil"


def fetch_all_contests():
    print("🔄 Buscando TODOS os concursos da Lotofácil...")
    response = requests.get(BASE_URL, headers=HEADERS, timeout=60)
    response.raise_for_status()

    data = response.json()

    concursos = []

    for raw in data:
        dezenas = sorted(int(d) for d in raw["dezenas"])
        concursos.append({
            "concurso": int(raw["concurso"]),
            "data": raw["data"],
            "dezenas": dezenas
        })

    concursos.sort(key=lambda x: x["concurso"])
    return concursos


def save_csv(concursos):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "concurso", "data",
            "d1", "d2", "d3", "d4", "d5",
            "d6", "d7", "d8", "d9", "d10",
            "d11", "d12", "d13", "d14", "d15"
        ])

        for c in concursos:
            writer.writerow([c["concurso"], c["data"]] + c["dezenas"])


def main():
    concursos = fetch_all_contests()
    print(f"✅ Total de concursos encontrados: {len(concursos)}")
    save_csv(concursos)
    print("💾 CSV atualizado com histórico completo")


if __name__ == "__main__":
    main()
