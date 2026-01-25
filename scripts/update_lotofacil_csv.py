name: Atualizar Lotofácil CSV

on:
  workflow_dispatch:
  schedule:
    - cron: "15 3 * * *" # todo dia 03:15 UTC (ajuste se quiser)

# Evita dois runs simultâneos (isso causa "fetch first" e push rejeitado)
concurrency:
  group: lotofacil-csv-update
  cancel-in-progress: true

# Permissão explícita para o GITHUB_TOKEN conseguir dar push
permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - name: Checkout
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: true

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

      - name: Commit e push se houver mudanças (com retry e rebase)
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -e

          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          # Se não mudou nada, encerra sem erro
          git add data/lotofacil.csv || true
          if git diff --cached --quiet; then
            echo "Nenhuma mudança para commitar."
            exit 0
          fi

          git commit -m "Atualizar lotofacil.csv automaticamente" || true

          # Tenta algumas vezes porque o remoto pode mudar no meio do run
          for i in 1 2 3 4 5 6; do
            echo "Tentativa $i/6: sincronizando e fazendo push..."

            # Puxa o estado atual do remoto e rebaseia (com autostash)
            git fetch origin main
            git pull --rebase --autostash origin main || true

            # Tenta subir
            if git push origin HEAD:main; then
              echo "Push realizado com sucesso."
              exit 0
            fi

            echo "Push falhou (provável atualização concorrente). Aguardando e tentando de novo..."
            sleep $((i * 5))
          done

          echo "Falha após 6 tentativas de push."
          exit 1
