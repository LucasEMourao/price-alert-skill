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

## Fluxo atual

1. Instale as dependencias Python e o Chromium do Playwright.
2. Configure o `.env`.
3. Na primeira vez, faca o login manual do Mercado Livre com `python3 scripts/generate_melila_links.py --login`.
4. Na primeira vez, faca o login inicial do WhatsApp com `python3 scripts/sender_worker.py --continuous --headed`.
5. Rode `scripts/scan_deals.py` com `--scan-only`.
6. Deixe `scripts/sender_worker.py --continuous` consumindo a fila.
7. As mensagens saem com imagem + legenda + link.

## Scripts principais

- `scripts/scan_deals.py` - scan, classificacao e populacao dos pools
- `scripts/deal_selection.py` - queries, categorias, thresholds e prioridades
- `scripts/deal_queue.py` - pools expiráveis e metadata da cadencia
- `scripts/sender_worker.py` - sender unico e serial do WhatsApp
- `scripts/dispatch_pending_deals.py` - drenagem pontual de poucas mensagens
- `scripts/fetch_amazon_br.py` - scraping da Amazon BR
- `scripts/fetch_ml_browser.py` - scraping do Mercado Livre
- `scripts/generate_melila_links.py` - geracao de `meli.la`
- `scripts/send_to_whatsapp.py` - automacao do WhatsApp Web
- `scripts/utils.py` - utilitarios de formatacao, cooldown e persistencia
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

## Automacao Windows

Tarefas esperadas:

- `PriceAlert Sender Worker`
- `PriceAlert Scan 15m`
- `PriceAlert Sender Stop`

Launchers locais:

- `C:\Users\bruno\PriceAlertTasks\sender.ps1`
- `C:\Users\bruno\PriceAlertTasks\scan.ps1`
- `C:\Users\bruno\PriceAlertTasks\stop.ps1`

## Melhorias futuras registradas

- shutdown mais gracioso no fim da janela de envio
- melhor resumo operacional nos logs
- utilitario unico de diagnostico
- documentacao de reinstalacao das tasks e launchers curtos
