#!/usr/bin/env python3
"""Atualiza o CSV pela CAIXA, recuperando lacunas sem alterar linhas existentes."""

import argparse
import csv
from datetime import datetime
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request

API_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"
CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "lotofacil.csv"
HEADER = ["concurso", "data", *[f"d{i}" for i in range(1, 16)]]
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


class ValidationError(ValueError):
    pass


def positive_id(value):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]*", str(value)):
        raise ValidationError(f"Identificador de concurso inválido: {value!r}")
    return int(value)


def draw_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", value):
        raise ValidationError(f"Data inválida: {value!r}")
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError as exc:
        raise ValidationError(f"Data inválida: {value!r}") from exc


def numbers(values):
    if not isinstance(values, (list, tuple)) or len(values) != 15:
        raise ValidationError("O concurso precisa conter exatamente 15 dezenas.")
    if any(isinstance(n, bool) or not re.fullmatch(r"[0-9]{1,2}", str(n)) for n in values):
        raise ValidationError("Dezenas precisam ser números inteiros.")
    result = tuple(sorted(int(n) for n in values))
    if len(set(result)) != 15 or not all(1 <= n <= 25 for n in result):
        raise ValidationError("Dezenas repetidas ou fora de 1 a 25.")
    return result


def official_record(data, expected=None):
    if not isinstance(data, dict):
        raise ValidationError("Resposta da CAIXA não é um objeto JSON.")
    try:
        number = positive_id(data["numero"])
        if expected is not None and number != expected:
            raise ValidationError(f"Esperado concurso {expected}, recebido {number}.")
        date = data["dataApuracao"]
        draw_date(date)
        result = numbers(data["listaDezenas"])
    except KeyError as exc:
        raise ValidationError(f"Campo ausente na resposta: {exc}") from exc
    return number, date, result


def fetch(number=None):
    url = API_URL + (f"/{number}" if number is not None else "")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise RuntimeError(f"Falha ao consultar {url}: {exc}") from exc
            time.sleep(2 ** attempt)


def read_csv(path):
    """Retorna registros normalizados e suas linhas originais, sem reserializá-las."""
    raw = path.read_bytes() if path.exists() else b""
    if not raw:
        return raw, (",".join(HEADER) + "\n").encode(), {}, {}
    lines = raw.splitlines(keepends=True)
    try:
        header = next(csv.reader([lines[0].decode("utf-8-sig")], strict=True))
        if header != HEADER:
            raise ValidationError("Cabeçalho CSV inesperado.")
        records, original = {}, {}
        previous = 0
        for line in lines[1:]:
            row = next(csv.reader([line.decode("utf-8")], strict=True))
            if len(row) != 17:
                raise ValidationError("Linha CSV precisa conter 17 campos.")
            number = positive_id(row[0])
            if number <= previous:
                raise ValidationError("Concursos repetidos ou fora de ordem.")
            draw_date(row[1])
            records[number] = (number, row[1], numbers(row[2:]))
            original[number] = line
            previous = number
    except (UnicodeError, csv.Error) as exc:
        raise ValidationError(f"CSV inválido: {exc}") from exc
    validate_dates(records)
    return raw, lines[0], records, original


def validate_dates(records):
    previous = None
    for number in sorted(records):
        current = draw_date(records[number][1])
        if previous is not None and current < previous:
            raise ValidationError(f"Data fora de ordem no concurso {number}.")
        previous = current


def validate_continuity(records):
    if not records:
        raise ValidationError("CSV sem concursos.")
    missing = sorted(set(range(1, max(records) + 1)) - records.keys())
    if missing:
        raise ValidationError(f"Concursos ausentes: {missing}")


def validate_file(path=CSV_PATH):
    _, _, records, _ = read_csv(Path(path))
    validate_continuity(records)
    return len(records), max(records)


def row_bytes(record):
    number, date, values = record
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\r\n").writerow(
        [number, date, *[f"{n:02d}" for n in values]]
    )
    return stream.getvalue().encode("utf-8")


def atomic_write(path, content, before):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if path.exists():
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        if (path.read_bytes() if path.exists() else b"") != before:
            raise ValidationError("O CSV mudou durante a atualização; execute novamente.")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update(path=CSV_PATH, fetcher=fetch):
    path = Path(path)
    before, header, records, original = read_csv(path)
    latest = official_record(fetcher())
    latest_id = latest[0]
    if records:
        last_id = max(records)
        if latest_id < last_id:
            raise ValidationError("API desatualizada: o último concurso é anterior ao CSV.")
        expected = latest if latest_id == last_id else official_record(fetcher(last_id), last_id)
        if records[last_id] != expected:
            raise ValidationError(f"Concurso {last_id} existente diverge da CAIXA; nenhuma linha foi alterada.")
    missing = sorted(set(range(1, latest_id + 1)) - records.keys())
    for number in missing:
        records[number] = latest if number == latest_id else official_record(fetcher(number), number)
    validate_dates(records)
    validate_continuity(records)
    if not missing:
        return []
    chunks = [header] + [original.get(n, row_bytes(records[n])) for n in sorted(records)]
    if any(not chunk.endswith((b"\n", b"\r")) for chunk in chunks[:-1]):
        raise ValidationError("Linha existente sem terminador; preservação exige revisão manual.")
    atomic_write(path, b"".join(chunks), before)
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    parser.add_argument("--validate-only", action="store_true", help="Valida o CSV sem acessar a rede ou modificar arquivos.")
    args = parser.parse_args()
    try:
        added = [] if args.validate_only else update(args.csv)
        count, last = validate_file(args.csv)
        print(f"CSV válido: {count} concursos consecutivos (1–{last}).")
        print(f"Concursos adicionados: {added}" if added else "Nenhuma alteração.")
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
