# Context - price-alert-skill

## Resumo

`price-alert-skill` e um pipeline de scraping para marketplaces brasileiros com entrega automatizada em WhatsApp.

O fluxo atual nao envia do scan diretamente. Ele trabalha em duas etapas:

1. `scripts/scan_deals.py --scan-only` busca ofertas, classifica e alimenta pools expiráveis.
2. `scripts/sender_worker.py --continuous` e o unico processo que consome a fila e envia uma mensagem por vez para o WhatsApp Web.

O formato de envio mantido hoje e:

- imagem
- legenda
- link de afiliado

## Fluxo vigente

1. `scripts/scan_deals.py` faz a busca nas queries monitoradas.
2. Amazon BR e coletada por `scripts/fetch_amazon_br.py`.
3. Mercado Livre e coletado por `scripts/fetch_ml_browser.py`.
4. Links do Mercado Livre viram `meli.la` via `scripts/generate_melila_links.py`.
5. Cada oferta e normalizada por `scripts/deal_selection.py`.
6. As ofertas entram nas trilhas `urgent`, `priority`, `normal` ou `discarded`.
7. Os pools expiráveis sao persistidos por `scripts/deal_queue.py` em `data/deal_queue.json`.
8. `scripts/sender_worker.py` abre uma unica sessao do WhatsApp e envia em serie.
9. O historico de envio e controlado por `data/sent_deals.json`.

## Como a cadencia funciona

- `urgent`
  Entra na frente da fila e pode ser reenviada com cooldown mais curto.

- `priority`
  Entra na fila principal depois de `urgent`.

- `normal`
  Entra na fila com prioridade menor.

- `discarded`
  Nao entra na fila porque ficou abaixo das regras atuais.

O sender usa uma sequencia nao urgente `priority, priority, priority, normal`, preservando foco nas melhores oportunidades sem abandonar o restante.

## Estrutura relevante

```text
.agents/skills/price-alert-skill/
|-- SKILL.md
|-- CONTEXT.md
|-- PLANO.md
|-- .env.example
|-- run_scan.ps1
|-- run_sender.ps1
|-- stop_sender.ps1
|-- data/
|   |-- deal_queue.json
|   |-- sent_deals.json
|   |-- melila_cache.json
|   |-- ml_session.json
|   |-- messages/
|-- logs/
|-- references/
`-- scripts/
    |-- config.py
    |-- deal_queue.py
    |-- deal_selection.py
    |-- dispatch_pending_deals.py
    |-- fetch_amazon_br.py
    |-- fetch_ml_browser.py
    |-- generate_melila_links.py
    |-- scan_deals.py
    |-- send_to_whatsapp.py
    |-- sender_worker.py
    |-- utils.py
    `-- tests/
```

## Componentes ativos

- `scripts/scan_deals.py`
  Faz o scan, calcula desconto, aplica affiliate link, classifica por lane e atualiza os pools.

- `scripts/deal_selection.py`
  Define queries, categorias, regras de corte e prioridades.

- `scripts/deal_queue.py`
  Mantem os pools `urgent`, `priority` e `normal`, com expiracao e refresh por novos scans.

- `scripts/sender_worker.py`
  Processo unico de envio serial para o WhatsApp.

- `scripts/dispatch_pending_deals.py`
  Helper one-shot para drenar poucas mensagens e encerrar.

- `scripts/send_to_whatsapp.py`
  Camada de browser/Playwright para o WhatsApp Web.

- `scripts/generate_melila_links.py`
  Converte ofertas do Mercado Livre em links `meli.la`.

- `run_scan.ps1`
  Wrapper operacional do scan.

- `run_sender.ps1`
  Wrapper operacional do sender continuo.

- `stop_sender.ps1`
  Encerra o sender usando o lock `data/sender_worker.lock`.

## Componentes legados ou secundarios

- `scripts/scrape_server.py`
  Nao faz parte do fluxo principal atual.

- `scripts/fetch_mercadolivre_br.py`
  Parser legado. O caminho principal hoje e `fetch_ml_browser.py`.

## Estado persistido

- `data/deal_queue.json`
  Pools ativos e metadata do sender/scan.

- `data/sent_deals.json`
  Historico usado para cooldown e deduplicacao entre execucoes.

- `data/melila_cache.json`
  Cache de links `meli.la`.

- `data/ml_session.json`
  Sessao persistida do painel de afiliados do Mercado Livre.

- `data/messages/deals_*.json`
  Foto de cada rodada de scan.

## Automacao Windows vigente

Hoje o ambiente operacional usa tres tarefas do Windows:

- `PriceAlert Sender Worker`
  Inicia o sender continuo.

- `PriceAlert Scan 15m`
  Roda o scan a cada 15 minutos.

- `PriceAlert Sender Stop`
  Encerra o sender as 23:00.

Para contornar o limite de tamanho do `schtasks /TR`, as tasks chamam launchers locais em:

- `C:\Users\bruno\PriceAlertTasks\sender.ps1`
- `C:\Users\bruno\PriceAlertTasks\scan.ps1`
- `C:\Users\bruno\PriceAlertTasks\stop.ps1`

Esses arquivos sao parte da configuracao operacional da maquina. Se o caminho do repositorio mudar, eles precisam ser recriados ou atualizados.

## Comandos de referencia

```bash
# Instalar dependencias
pip install -r requirements.txt
playwright install chromium

# Login manual no Mercado Livre afiliados
python3 scripts/generate_melila_links.py --login

# Scan pontual de uma query
python3 scripts/scan_deals.py "monitor gamer" --min-discount 10 --scan-only

# Scan completo da cadencia
python3 scripts/scan_deals.py --all --scan-only --min-discount 10 --max-results 8

# Sender continuo
python3 scripts/sender_worker.py --continuous

# Sender com navegador visivel
python3 scripts/sender_worker.py --continuous --headed

# Drenagem pontual
python3 scripts/dispatch_pending_deals.py --max-messages 4
```

## Decisoes importantes

- O scan e o envio foram separados.
- Existe apenas um sender do WhatsApp por vez.
- A automacao prioriza estabilidade do WhatsApp acima de throughput maximo.
- O grupo padrao vem de `WHATSAPP_GROUP` no `.env`.
- O sender roda oculto no Windows, sem depender de janela visivel.

## Melhorias futuras registradas

- Encerramento mais gracioso do sender as 23:00 para evitar o ruido final do driver/Node no log.
- Melhor observabilidade no scan com timestamp explicito de fim de rodada.
- Melhor observabilidade no sender com resumo por hora e total drenado da fila.
- Comando de diagnostico unico para status de tasks, fila e logs.
- Opcionalmente mover os launchers de `C:\Users\bruno\PriceAlertTasks\` para um empacotamento mais reproduzivel.
