name: Atualizar Lotofácil CSV

on:
  workflow_dispatch:
  schedule:
    # Ajuste o horário se quiser (UTC). Ex: 03:20 UTC = 00:20 no Brasil (dependendo do fuso)
    - cron: "20 3 * * *"

permissions:
  contents: write

concurrency:
  group: lotofacil-csv-update
  cancel-in-progress: true

jobs:
  update:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout do repositório
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Instalar dependências
        run: |
          python -m pip install --upgrade pip
          pip install requests

      - name: Executar script de atualização
        run: |
          python scripts/update_lotofacil_csv.py

      - name: Commit e push se houver mudanças
        run: |
          git config user.name "github-actions"
          git config user.email "github-actions@github.com"

          if [[ -n "$(git status --porcelain data/lotofacil.csv)" ]]; then
            git add data/lotofacil.csv
            git commit -m "Atualizar lotofacil.csv automaticamente"
            git push origin main
          else
            echo "Nenhuma mudança no CSV, nada para commitar."
          fi
