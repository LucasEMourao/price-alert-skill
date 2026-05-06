# PLANO - price-alert-skill

## Objetivo

Buscar ofertas em marketplaces brasileiros, gerar links de afiliado, alimentar uma fila por cadencia e enviar mensagens para WhatsApp no formato:

- imagem
- legenda
- link de afiliado

## Estado atual

O fluxo principal hoje e este:

1. `scripts/scan_deals.py --scan-only` faz a coleta e popula a fila.
2. `price_alert_skill/core/domain/` aplica classificacao, ranking, dedup e politica de fila.
3. `price_alert_skill/core/application/` orquestra o scan e o sender.
4. `price_alert_skill/core/adapters/` implementa persistencia JSON, scanners, `meli.la` e WhatsApp.
5. `scripts/sender_worker.py --continuous` envia uma mensagem por vez para o WhatsApp.

Nao e necessario subir servidor auxiliar para esse fluxo.

## Ultimo checkpoint validado

Checkpoint operacional mais recente:

- sender com correcoes de UTF-8 e logging do Windows aplicadas
- suite mais recente: `171 passed`
- teste end-to-end real do sender:
  - `1` oferta Amazon BR enviada com sucesso
  - `1` oferta Mercado Livre enviada com sucesso
- screenshot de referencia:
  - `data/debug/e2e_verify_20260506_utf8.png`

Leitura pratica:

- o fluxo de mensagem `imagem + legenda + link` esta funcional
- a legenda sai correta do scan e chega correta ao WhatsApp
- o problema que ainda pode derrubar o dia inteiro nao e mais o sender, e sim energia/suspensao da maquina

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

Esses launchers apenas delegam para:

- `run_sender.ps1`
- `run_scan.ps1`
- `stop_sender.ps1`

Comportamento esperado:

- `run_scan.ps1` faz apenas uma rodada e encerra com o codigo do processo Python.
- `run_sender.ps1` funciona como supervisor do sender continuo, com relancamento automatico quando nao houve pedido de stop.
- `stop_sender.ps1` pede parada graciosa antes de recorrer a encerramento forcado.

### 7. Camadas da arquitetura

#### Dominio

Local: `price_alert_skill/core/domain/`

Concentra:
- lane rules
- ranking
- `product_key` e `offer_key`
- dedup, cooldown e resend policy
- expiracao e selecao da fila

#### Aplicacao

Local: `price_alert_skill/core/application/`

Concentra:
- `scan_use_case.py`
- `sender_use_case.py`

#### Ports

Local: `price_alert_skill/core/ports/`

Concentra:
- contratos para fila
- contratos para historico de enviados
- contratos para scanners
- contratos para afiliado
- contratos para envio de mensagem

#### Adapters

Local: `price_alert_skill/core/adapters/`

Concentra:
- JSON repositories
- scanners da Amazon e do Mercado Livre
- geracao de `meli.la`
- sender de WhatsApp

#### Entrypoints

Local: `price_alert_skill/core/entrypoints/`

Concentra:
- CLI de scan
- CLI de sender
- CLI de dispatch

#### Compatibilidade legado

Local: `scripts/`

Os scripts antigos continuam existindo, mas agora devem ser tratados como wrappers finos sobre a arquitetura nova. O bootstrap deles fica em `scripts/_package_bootstrap.py`, que aponta para o pacote repo-level `price_alert_skill/`.

### 8. Monitoracao diaria

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

Observacoes:

- os timestamps desses logs estao em UTC
- mojibake no console do Windows pode afetar a leitura visual dos caracteres, mas nao implica falha operacional por si so
- se um log do mesmo dia misturar trechos antigos e novos em codificacoes diferentes, valide pelo comportamento real do sender, pelo JSON salvo em `data/messages/` e pela fila

```powershell
$q = Get-Content ".\data\deal_queue.json" -Raw | ConvertFrom-Json
[pscustomobject]@{
  urgent = @($q.urgent_pool).Count
  priority = @($q.priority_pool).Count
  normal = @($q.normal_pool).Count
  last_scan_at = $q.meta.last_scan_at
  last_sender_tick_at = $q.meta.last_sender_tick_at
} | Format-List
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
- alterar os wrappers Windows sempre que a regra de negocio mudar

## Proximo foco recomendado

Depois deste checkpoint, o proximo trabalho recomendado e:

1. impedir suspensao/hibernacao do Windows durante a janela operacional
2. validar se as tasks continuam rodando com a tela desligada ou bloqueada
3. so depois pensar em melhorias extras de throughput ou observabilidade

## Melhorias futuras desejaveis

- simplificar a composicao das dependencias em um bootstrap unico
- shutdown mais gracioso no stop de 23:00
- healthcheck ou watchdog do sender
- comando de diagnostico consolidado para tasks, fila, lock e logs
- relatorio operacional diario resumido
- documentar e automatizar melhor a recriacao dos launchers curtos
- aumentar observabilidade de fim de scan e idle do sender
- avaliar migracao de JSON para SQLite se a concorrencia aumentar
