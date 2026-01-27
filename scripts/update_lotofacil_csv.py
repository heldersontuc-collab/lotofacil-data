import csv
import requests
from pathlib import Path

# ============================================================
# CONFIGURAÇÕES
# ============================================================

CSV_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"
OUTPUT_FILE = Path("data/lotofacil.csv")

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0"
}

# ============================================================
# FUNÇÕES
# ============================================================

def fetch_all_contests():
    """
    Busca TODOS os concursos da Lotofácil diretamente da Caixa
    """
    response = requests.get(CSV_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    data = response.json()

    concursos = []

    # Concurso atual
    concursos.append(parse_contest(data))

    # Concursos anteriores
    for c in data.get("listaResultado", []):
        concursos.append(parse_contest(c))

    # Remove duplicados pelo número do concurso
    concursos_dict = {c["concurso"]: c for c in concursos}

    # Ordena do concurso 1 até o último
    return sorted(concursos_dict.values(), key=lambda x: x["concurso"])


def parse_contest(raw):
    """
    Normaliza um concurso para o formato CSV
    """
    dezenas = raw.get("listaDezenas", [])

    return {
        "concurso": int(raw["numero"]),
        "data": raw["dataApuracao"],
        "dezenas": sorted(int(d) for d in dezenas)
    }


def save_csv(concursos):
    """
    Salva o CSV no padrão esperado pelo app
    """
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Cabeçalho
        writer.writerow([
            "concurso", "data",
            "d1", "d2", "d3", "d4", "d5",
            "d6", "d7", "d8", "d9", "d10",
            "d11", "d12", "d13", "d14", "d15"
        ])

        # Dados
        for c in concursos:
            writer.writerow(
                [c["concurso"], c["data"]] + c["dezenas"]
            )


# ============================================================
# MAIN
# ============================================================

def main():
    print("🔄 Buscando concursos da Lotofácil...")
    concursos = fetch_all_contests()
    print(f"✅ Total de concursos encontrados: {len(concursos)}")

    save_csv(concursos)
    print(f"💾 CSV atualizado em: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
