#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import csv
import os
import sys
import urllib.request

API_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"
CSV_PATH = "data/lotofacil.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

def fetch():
    req = urllib.request.Request(API_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def ensure_dir():
    os.makedirs("data", exist_ok=True)

def existing():
    if not os.path.exists(CSV_PATH):
        return set()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return {row["concurso"] for row in csv.DictReader(f)}

def write(data):
    concurso = str(data["numero"])
    if concurso in existing():
        print("Concurso já existe.")
        return False

    ensure_dir()
    dezenas = data["listaDezenas"]

    new_file = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["concurso", "data", *[f"d{i}" for i in range(1, 16)]])
        w.writerow([concurso, data["dataApuracao"], *dezenas])

    print("CSV atualizado.")
    return True

def main():
    try:
        data = fetch()
        write(data)
        sys.exit(0)
    except Exception as e:
        print("Erro:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
