# PLANO - price-alert-skill

## Objetivo

Buscar ofertas em marketplaces brasileiros, gerar links de afiliado, alimentar uma fila por cadencia e enviar mensagens para WhatsApp no formato:

- imagem
- legenda
- link de afiliado

## Estado atual

O fluxo principal hoje e este:

1. `scripts/scan_deals.py --scan-only` faz a busca e popula a fila.
2. `scripts/deal_selection.py` classifica as ofertas.
3. `scripts/deal_queue.py` mantem pools expiráveis.
4. `scripts/sender_worker.py --continuous` envia uma mensagem por vez para o WhatsApp.
5. `scripts/send_to_whatsapp.py` cuida da sessao e da entrega no WhatsApp Web.

Nao e necessario subir servidor auxiliar para esse fluxo.

## Plano operacional

### 1. Preparacao

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configuracao

Criar o `.env` a partir de `.env.example` e preencher pelo menos:

```env
AMAZON_AFFILIATE_TAG=sua-tag
WHATSAPP_GROUP=Nome do grupo
```

### 3. Login inicial do Mercado Livre

```bash
python3 scripts/generate_melila_links.py --login
```

### 4. Login inicial do WhatsApp

```bash
python3 scripts/sender_worker.py --continuous --headed
```

Use o QR code apenas na primeira vez ou quando a sessao expirar.

### 5. Teste manual minimo

```bash
python3 scripts/scan_deals.py "monitor gamer" --min-discount 10 --max-results 4 --scan-only
python3 scripts/sender_worker.py --continuous --headed
```

O esperado:

- o scan popula `data/deal_queue.json`
- o sender abre o grupo correto
- as mensagens saem com imagem + legenda + link

### 6. Rotina automatizada no Windows

Tarefas do Agendador:

- `PriceAlert Sender Worker`
  Inicia as 08:00

- `PriceAlert Scan 15m`
  Inicia as 08:00 e repete a cada 15 minutos ate 22:45

- `PriceAlert Sender Stop`
  Executa as 23:00

As tasks chamam launchers locais em:

- `C:\Users\bruno\PriceAlertTasks\sender.ps1`
- `C:\Users\bruno\PriceAlertTasks\scan.ps1`
- `C:\Users\bruno\PriceAlertTasks\stop.ps1`

### 7. Monitoracao diaria

Conferir:

- status das tasks
- crescimento e drenagem da fila
- volume real no grupo
- se o sender para as 23:00

Comandos uteis:

```powershell
schtasks /Query /TN "PriceAlert Sender Worker" /V /FO LIST
schtasks /Query /TN "PriceAlert Scan 15m" /V /FO LIST
schtasks /Query /TN "PriceAlert Sender Stop" /V /FO LIST
```

```powershell
Get-Content ".\logs\sender-YYYY-MM-DD.log" -Tail 50
Get-Content ".\logs\scan-YYYY-MM-DD.log" -Tail 50
```

## Arquivos importantes

- `data/deal_queue.json` - pools ativos da cadencia
- `data/sent_deals.json` - historico e cooldown
- `data/melila_cache.json` - cache de links `meli.la`
- `data/ml_session.json` - sessao do Mercado Livre afiliados
- `data/messages/` - fotos de cada rodada
- `logs/` - saida operacional de scan e sender

## O que nao faz parte do plano atual

- enviar direto do scan como fluxo principal
- rodar varios senders em paralelo
- depender de servidor auxiliar para scraping

## Melhorias futuras desejaveis

- shutdown mais gracioso no stop de 23:00
- relatorio operacional diario resumido
- documentar e automatizar melhor a recriacao dos launchers curtos
- aumentar observabilidade de fim de scan e idle do sender
