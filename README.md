# Lotofácil – Base de dados

Histórico dos concursos em `data/lotofacil.csv`, consultado na API oficial da CAIXA:
https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil

## Formato

- Separador: vírgula.
- Colunas: `concurso`, `data`, `d1` até `d15`.
- Data: `DD/MM/YYYY`.
- Dezenas: 15 números distintos entre 01 e 25.
- Concursos ordenados e consecutivos a partir de 1.

URL direta:
https://raw.githubusercontent.com/heldersontuc-collab/lotofacil-data/main/data/lotofacil.csv

## Atualização e verificações

Requer Python 3.11 ou posterior, sem dependências externas:

```sh
python -m unittest discover -s tests -v
python scripts/update_lotofacil_csv.py --validate-only
python scripts/update_lotofacil_csv.py
```

O atualizador consulta o último resultado e busca cada concurso ausente pelo
endpoint numerado da CAIXA. Valida identificador, data, dezenas, ordem e continuidade
antes de gravar. Confere o último registro existente com a fonte e interrompe em
caso de divergência. As linhas existentes são preservadas literalmente; o arquivo
é substituído atomicamente somente depois da conclusão de todas as verificações.
Erros de rede, resultados inconsistentes ou API anterior à base não são tratados
como atualização bem-sucedida. Uma linha sem terminador que precisaria receber uma
nova linha após ela exige revisão manual para preservar os bytes originais.

`.github/workflows/update-lotofacil.yml` é o único atualizador agendado. Mantém as
janelas de 01:05 e 03:10 UTC e aceita execução manual. O GitHub pode atrasar horários
agendados. As execuções são serializadas, sem cancelar a que já está em andamento.
Em conflito de publicação, o checkout descartável do runner volta ao `main` atual
e regenera o CSV; nunca usa force-push nem mescla dois CSVs gerados.

`teste.yml` executa testes e validação local em pushes, pull requests e execuções
manuais, com permissão somente de leitura. Não atualiza a base nem consulta a rede.
Os testes usam Git local para simular concorrência e perda da resposta de um push.

## Proveniência e limites

A recuperação de oito lacunas em 06/11/2026 está registrada em
`data/audits/2026-11-06-gap-repair.json`, com URLs, horários, resultados e hashes.
Foram preservadas as 3.814 linhas existentes e adicionados os concursos
3715, 3759, 3766, 3771, 3790, 3791, 3792 e 3794, obtidos diretamente da CAIXA.

A continuidade e a estrutura são verificadas em cada execução. Isso não equivale
a reconferir todas as linhas históricas com a CAIXA, nem comprova capacidade
preditiva de qualquer motor que consuma a base. O reparo não recalcula carteiras,
painéis ou estudos retrospectivos e não altera suas regras.

Execute apenas um atualizador local por arquivo: a verificação de mudança local
não substitui um bloqueio entre processos. A serialização das execuções agendadas
é garantida pelo grupo de concorrência do workflow. Pushes do próprio
`GITHUB_TOKEN` normalmente não disparam outro workflow; por isso o atualizador
executa seus próprios testes e validações antes da publicação.
