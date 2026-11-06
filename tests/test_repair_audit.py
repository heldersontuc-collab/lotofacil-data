"""Protege os resultados recuperados sem congelar o hash de futuras atualizações."""
import csv
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RepairAuditTests(unittest.TestCase):
    def test_recovered_results_still_match_official_evidence(self):
        audit = json.loads((ROOT / 'data/audits/2026-11-06-gap-repair.json').read_text())
        with (ROOT / 'data/lotofacil.csv').open(newline='', encoding='utf-8-sig') as handle:
            records = {int(row['concurso']): row for row in csv.DictReader(handle)}
        self.assertEqual(sorted(item['numero'] for item in audit['sources']), audit['inserted_contests'])
        for source in audit['sources']:
            number = source['numero']
            row = records[number]
            self.assertEqual(row['data'], source['dataApuracao'])
            self.assertEqual(sorted(int(row[f'd{i}']) for i in range(1, 16)), sorted(map(int, source['listaDezenas'])))
            self.assertEqual(source['source_url'], f'https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/{number}')


if __name__ == '__main__':
    unittest.main()
