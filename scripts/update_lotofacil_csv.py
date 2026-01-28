#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Atualiza o CSV da Lotofácil no repositório.

Comportamento "à prova de API":
- Se a API estiver fora do ar (503/timeout/etc), o script NÃO falha.
- Mantém o CSV atual como está e encerra com exit code 0.
- Se conseguir baixar, converte e escreve o CSV apenas se houver mudança.

Saída CSV (padrão):
data/lotofacil.csv

Formato CSV:
concurso,data,d1,d2,...,d15
"""

from __future__ import annotations

import csv
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


# ======================================================================
# CONFIG
# ======================================================================

API_URL_DEFAULT = "https://loteriascaixa-api.herokuapp.com/api/lotofacil"
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_CSV_PATH_DEFAULT = os.path.join(REPO_ROOT, "data", "lotofacil.csv")

REQUEST_TIMEOUT_SEC = 20
RETRY_COUNT = 3
RETRY_SLEEP_SEC = 3


# ======================================================================
# UTIL
# ======================================================================

def log(msg: str) -> None:
    print(msg, flush=True)


def read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def safe_int(x: Any) -> Optional[int]:
    try:
        return int(str(x).strip())
    except Exception:
        return None


# ======================================================================
# FETCH / PARSE
# ======================================================================

def fetch_all_contests(api_url: str) -> Optional[Any]:
    """
    Retorna JSON da API, ou None se não conseguir (sem quebrar o workflow).
    """
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "User-Agent": "thoth-ia-lotofacil-updater/1.0",
    }

    last_err: Optional[Exception] = None

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            log(f"🌐 Buscando concursos na API (tentativa {attempt}/{RETRY_COUNT})...")
            res = requests.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT_SEC)
            # NÃO levantar exceção se vier 503 e quiser logar melhor:
            if res.status_code != 200:
                log(f"⚠️ API respondeu status {res.status_code}. Corpo (parcial): {res.text[:120]!r}")
                # se for última tentativa, devolve None
                last_err = Exception(f"HTTP {res.status_code}")
            else:
                data = res.json()
                if data is None:
                    log("⚠️ API retornou JSON vazio.")
                    return None
                return data

        except Exception as e:
            last_err = e
            log(f"⚠️ Erro ao buscar API: {e}")

        if attempt < RETRY_COUNT:
            time.sleep(RETRY_SLEEP_SEC)

    log(f"🧊 Falha definitiva na API. Mantendo CSV atual. Motivo: {last_err}")
    return None


def normalize_contests(api_json: Any) -> List[Tuple[int, str, List[int]]]:
    """
    Converte o JSON (formato variável) em uma lista:
    (numero, data_str, dezenas[15])

    Aceita variações comuns da API:
    - {"concurso": 3598, "data": "2026-01-28", "dezenas": [..]}
    - {"numero": 3598, "data": "...", "listaDezenas": ["01","02",...]}
    - {"concurso": 3598, "data": "...", "dezenas": ["01", ...]}
    - Lista de concursos ou objeto com chave "concursos"/"data"
    """
    contests_raw: Any = api_json

    # Se vier num wrapper
    if isinstance(contests_raw, dict):
        for key in ("concursos", "data", "resultados", "items", "lista"):
            if key in contests_raw and isinstance(contests_raw[key], list):
                contests_raw = contests_raw[key]
                break

    if not isinstance(contests_raw, list):
        log("⚠️ JSON não é lista de concursos. Não vou atualizar.")
        return []

    out: List[Tuple[int, str, List[int]]] = []

    for item in contests_raw:
        if not isinstance(item, dict):
            continue

        numero = (
            safe_int(item.get("concurso")) or
            safe_int(item.get("numero")) or
            safe_int(item.get("numeroConcurso")) or
            safe_int(item.get("id"))
        )
        if numero is None:
            continue

        data_str = (
            str(item.get("data") or item.get("dataApuracao") or item.get("dtApuracao") or "")
        ).strip()

        dezenas_any = (
            item.get("dezenas") or
            item.get("listaDezenas") or
            item.get("numeros") or
            item.get("bolas") or
            item.get("resultado")
        )

        dezenas: List[int] = []

        if isinstance(dezenas_any, list):
            for v in dezenas_any:
                iv = safe_int(v)
                if iv is not None:
                    dezenas.append(iv)

        # Algumas APIs mandam em string "01-02-..."
        elif isinstance(dezenas_any, str):
            parts = dezenas_any.replace(";", ",").replace("-", ",").split(",")
            for p in parts:
                iv = safe_int(p)
                if iv is not None:
                    dezenas.append(iv)

        if len(dezenas) != 15:
            continue

        dezenas = sorted(dezenas)
        out.append((numero, data_str, dezenas))

    out.sort(key=lambda x: x[0])
    return out


def contests_to_csv(contests: List[Tuple[int, str, List[int]]]) -> str:
    """
    Gera o conteúdo CSV.
    """
    # Header padrão
    header = ["concurso", "data"] + [f"d{i}" for i in range(1, 16)]

    # Vamos escrever em memória
    from io import StringIO
    buf = StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)

    for numero, data_str, dezenas in contests:
        row = [numero, data_str] + [f"{d:02d}" for d in dezenas]
        w.writerow(row)

    return buf.getvalue()


# ======================================================================
# MAIN
# ======================================================================

def main() -> int:
    api_url = os.environ.get("LOTOFACIL_API_URL", API_URL_DEFAULT).strip()
    out_csv_path = os.environ.get("OUT_CSV_PATH", OUT_CSV_PATH_DEFAULT).strip()

    log("===============================================")
    log("🦉 THOTH IA • Atualizador do CSV da Lotofácil")
    log(f"📌 API: {api_url}")
    log(f"📌 CSV: {out_csv_path}")
    log("===============================================")

    existing_csv = read_text(out_csv_path)
    if existing_csv:
        # tenta descobrir último concurso do CSV atual (best-effort)
        try:
            lines = [ln.strip() for ln in existing_csv.splitlines() if ln.strip()]
            last_line = lines[-1]
            parts = last_line.split(",")
            last_num = parts[0] if parts else "?"
            log(f"📦 CSV atual detectado. Última linha concurso: {last_num}")
        except Exception:
            pass
    else:
        log("📦 CSV atual não encontrado (primeira geração ou caminho diferente).")

    api_json = fetch_all_contests(api_url)
    if api_json is None:
        log("✅ Encerrando SEM atualizar (API indisponível). Workflow não falha.")
        return 0

    contests = normalize_contests(api_json)
    if not contests:
        log("⚠️ Não consegui normalizar concursos. Mantendo CSV atual.")
        return 0

    new_csv = contests_to_csv(contests)

    # Se não mudou, não regrava (evita commit sem necessidade)
    if new_csv.strip() == existing_csv.strip():
        log("✅ CSV já está atualizado. Nenhuma mudança detectada.")
        log(f"📊 Itens: {len(contests)} | last={contests[-1][0]}")
        return 0

    write_text(out_csv_path, new_csv)
    log("✅ CSV atualizado com sucesso!")
    log(f"📊 Itens: {len(contests)} | last={contests[-1][0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
