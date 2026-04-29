---
name: price-alert-monitor
description: Busque ofertas na Amazon BR e no Mercado Livre, gere links de afiliado e alimente um fluxo de envio serial para WhatsApp.
---

# Price Alert Monitor

Skill para busca sob demanda de ofertas em marketplaces brasileiros com automacao de envio para WhatsApp.

## O que a skill faz

- Busca ofertas na Amazon BR e no Mercado Livre
- Extrai preco atual e preco anterior exibido pelo marketplace
- Filtra por desconto minimo
- Gera links de afiliado da Amazon BR e links `meli.la` do Mercado Livre
- Classifica cada oferta em `urgent`, `priority`, `normal` ou `discarded`
- Alimenta uma fila expirável
- Envia mensagens para WhatsApp em fluxo serial

## Arquitetura atual

### Dominio

Local: `core/domain/`

Contem:
- `models.py`
- `types.py`
- `lane_rules.py`
- `identity.py`
- `ranking.py`
- `dedup_policy.py`
- `queue_policy.py`

Essa camada contem a regra de negocio pura e nao deve depender de Playwright, PowerShell ou JSON.

### Aplicacao

Local: `core/application/`

Contem:
- `scan_use_case.py`
- `sender_use_case.py`

Essa camada orquestra os casos de uso do projeto.

### Ports

Local: `core/ports/`

Contem os contratos para:
- fila
- historico de enviados
- scanners
- afiliado
- envio de mensagem
- relogio

### Adapters

Local: `core/adapters/`

Contem as integracoes concretas:
- JSON
- Amazon BR
- Mercado Livre
- `meli.la`
- WhatsApp Web

### Entrypoints

Local: `core/entrypoints/`

Contem:
- `scan_cli.py`
- `sender_cli.py`
- `dispatch_cli.py`

### Compatibilidade

Os scripts antigos em `scripts/` continuam existindo, mas agora funcionam como cascas finas e pontos de compatibilidade:

- `scripts/scan_deals.py`
- `scripts/sender_worker.py`
- `scripts/dispatch_pending_deals.py`

## Fluxo atual

1. Instale as dependencias Python e o Chromium do Playwright.
2. Configure o `.env`.
3. Na primeira vez, faca o login manual do Mercado Livre com `python3 scripts/generate_melila_links.py --login`.
4. Na primeira vez, faca o login inicial do WhatsApp com `python3 scripts/sender_worker.py --continuous --headed`.
5. Rode `scripts/scan_deals.py` com `--scan-only`.
6. Deixe `scripts/sender_worker.py --continuous` consumindo a fila.
7. As mensagens saem com imagem + legenda + link.

## Scripts principais

- `scripts/scan_deals.py` - wrapper de compatibilidade para o scan
- `scripts/deal_selection.py` - facade historica de selecao
- `scripts/deal_queue.py` - facade historica de fila
- `scripts/sender_worker.py` - wrapper de compatibilidade para o sender
- `scripts/dispatch_pending_deals.py` - wrapper de compatibilidade para dispatch one-shot
- `scripts/fetch_amazon_br.py` - scraper legado ainda usado pela integracao
- `scripts/fetch_ml_browser.py` - scraper legado ainda usado pela integracao
- `scripts/generate_melila_links.py` - fluxo de login e utilitario de afiliado
- `scripts/send_to_whatsapp.py` - camada Playwright historica do WhatsApp Web
- `scripts/utils.py` - facades e utilitarios historicos
- `scripts/config.py` - leitura do `.env`

## Variaveis de ambiente

- `AMAZON_AFFILIATE_TAG` - tag da Amazon BR
- `WHATSAPP_GROUP` - grupo padrao de envio
- `ML_PROXY` - proxy opcional
- `ML_AFFILIATE_EMAIL` e `ML_AFFILIATE_PASSWORD` - mantidas para referencia do fluxo de afiliados

## Instalacao

```bash
pip install -r requirements.txt
playwright install chromium
```

## Comandos uteis

```bash
# Login no Mercado Livre afiliados
python3 scripts/generate_melila_links.py --login

# Scan de uma categoria
python3 scripts/scan_deals.py "monitor gamer" --min-discount 10 --max-results 4 --scan-only

# Scan completo da cadencia
python3 scripts/scan_deals.py --all --scan-only --min-discount 10 --max-results 8

# Sender continuo
python3 scripts/sender_worker.py --continuous

# Sender continuo com navegador visivel
python3 scripts/sender_worker.py --continuous --headed

# Drenagem pontual
python3 scripts/dispatch_pending_deals.py --max-messages 4
```

## Categorias monitoradas por `--all`

- `mouse gamer`
- `teclado mecanico gamer`
- `mousepad gamer`
- `headset gamer`
- `webcam full hd`
- `microfone usb`
- `air cooler`
- `ssd nvme 1tb`
- `ssd nvme 2tb`
- `ssd sata 1tb`
- `ssd 2tb`
- `memoria ram ddr4`
- `memoria ram ddr5`
- `fonte 650w`
- `fonte 750w`
- `gabinete gamer`
- `water cooler`
- `monitor gamer`
- `processador ryzen`
- `processador intel core`
- `placa mae am5`
- `placa mae lga1700`
- `placa de video rtx`
- `placa de video rx`
- `notebook gamer`
- `pc gamer`
- `computador gamer`
- `desktop gamer`

## Formato da mensagem

```text
{emoji} OFERTA DO DIA

{emoji} {NOME_DO_PRODUTO}

{PERCENTUAL}% OFF
Antes: ~R$ {PRECO_ANTERIOR}~
Hoje: R$ {PRECO_ATUAL}

Comprar aqui:
{LINK}

Valores podem variar. Se entrar em estoque baixo, some rapido.
```

## Observacoes operacionais

- O sender e unico. Nao rode varios senders em paralelo.
- O scan nao envia diretamente no fluxo principal.
- O sender roda melhor como processo continuo no Windows.
- A deduplicacao nao usa so o titulo; ela considera produto e oferta.
- A fila fica em `data/deal_queue.json`.
- O historico de cooldown fica em `data/sent_deals.json`.
- As tasks do Windows usam launchers curtos em `C:\Users\bruno\PriceAlertTasks\`.

## Automacao Windows

Tarefas esperadas:

- `PriceAlert Sender Worker`
- `PriceAlert Scan 15m`
- `PriceAlert Sender Stop`

Launchers locais:

- `C:\Users\bruno\PriceAlertTasks\sender.ps1`
- `C:\Users\bruno\PriceAlertTasks\scan.ps1`
- `C:\Users\bruno\PriceAlertTasks\stop.ps1`

Wrappers reais no repositorio:

- `run_sender.ps1`
- `run_scan.ps1`
- `stop_sender.ps1`

## Melhorias futuras registradas

- simplificar a composicao das dependencias em um bootstrap central
- shutdown mais gracioso no fim da janela de envio
- healthcheck ou watchdog do sender
- melhor resumo operacional nos logs
- utilitario unico de diagnostico
- documentacao de reinstalacao das tasks e launchers curtos
- avaliar persistencia mais robusta se o volume crescer
