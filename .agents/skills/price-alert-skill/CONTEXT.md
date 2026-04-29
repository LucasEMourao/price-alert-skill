# Context - price-alert-skill

## Resumo

`price-alert-skill` e um pipeline de discovery de ofertas para marketplaces brasileiros com entrega automatizada em WhatsApp.

O fluxo principal vigente trabalha em duas etapas:

1. `scripts/scan_deals.py --scan-only` faz a coleta, classifica as ofertas e atualiza os pools expiráveis.
2. `scripts/sender_worker.py --continuous` e o unico processo que consome a fila e envia uma mensagem por vez para o WhatsApp Web.

O formato de envio mantido hoje e:

- imagem
- legenda
- link de afiliado

## Arquitetura atual

A arquitetura foi refatorada para separar regra de negocio, casos de uso e integracoes concretas.

### 1. Dominio puro

Local: `core/domain/`

Responsabilidades:
- entidades e tipos de negocio
- classificacao de lane
- `product_key` e `offer_key`
- ranking e ordenacao
- cooldown, dedup e politica de reenvio
- expiracao e selecao de fila

Arquivos principais:
- `models.py`
- `types.py`
- `lane_rules.py`
- `identity.py`
- `ranking.py`
- `dedup_policy.py`
- `queue_policy.py`

### 2. Aplicacao

Local: `core/application/`

Responsabilidades:
- orquestrar o fluxo de scan
- orquestrar o fluxo do sender
- coordenar dominio + repositorios + adaptadores

Arquivos principais:
- `scan_use_case.py`
- `sender_use_case.py`

### 3. Ports

Local: `core/ports/`

Responsabilidades:
- definir contratos para persistencia, scan, afiliado, relogio e envio

Arquivos principais:
- `queue_repository.py`
- `sent_deals_repository.py`
- `scanner.py`
- `affiliate_links.py`
- `message_sender.py`
- `clock.py`

### 4. Adapters

Local: `core/adapters/`

Responsabilidades:
- implementar os ports com tecnologia concreta
- encapsular JSON, Playwright e automacao externa

Arquivos principais:
- `json_queue_repository.py`
- `json_sent_deals_repository.py`
- `amazon_scanner.py`
- `mercadolivre_scanner.py`
- `meli_affiliate_links.py`
- `whatsapp_sender.py`

### 5. Entrypoints

Local: `core/entrypoints/`

Responsabilidades:
- montar dependencias
- expor CLI fina sobre application + adapters

Arquivos principais:
- `scan_cli.py`
- `sender_cli.py`
- `dispatch_cli.py`

### 6. Scripts legados como compatibilidade

Local: `scripts/`

Os scripts historicos continuam existindo, mas agora devem ser tratados como cascas finas e pontos de compatibilidade operacional.

Arquivos principais:
- `scan_deals.py`
- `sender_worker.py`
- `dispatch_pending_deals.py`

Eles delegam para a arquitetura nova e preservam:
- comandos ja usados
- wrappers PowerShell
- tarefas do Windows

## Fluxo vigente

1. `scripts/scan_deals.py` dispara o scan pelo entrypoint atual.
2. Os scanners concretos da Amazon BR e do Mercado Livre rodam pelos adapters.
3. Links do Mercado Livre podem virar `meli.la` pelo adapter de afiliado.
4. O dominio classifica cada oferta em `urgent`, `priority`, `normal` ou `discarded`.
5. O repositorio JSON atualiza `data/deal_queue.json`.
6. `scripts/sender_worker.py` sobe o sender continuo.
7. O sender escolhe a proxima oferta pela politica de fila.
8. O adapter de WhatsApp envia a mensagem.
9. O historico de envio e persistido em `data/sent_deals.json`.

## Como a cadencia funciona

- `urgent`
  Entra na frente da fila e usa cooldown menor.

- `priority`
  Entra na fila principal depois de `urgent`.

- `normal`
  Entra na fila com prioridade menor.

- `discarded`
  Nao entra na fila porque ficou abaixo das regras atuais.

O sender usa a sequencia nao urgente `priority, priority, priority, normal`, preservando foco nas melhores oportunidades sem abandonar o restante.

## Estrutura relevante

```text
.agents/skills/price-alert-skill/
|-- SKILL.md
|-- CONTEXT.md
|-- PLANO.md
|-- run_scan.ps1
|-- run_sender.ps1
|-- stop_sender.ps1
|-- core/
|   |-- domain/
|   |-- application/
|   |-- ports/
|   |-- adapters/
|   `-- entrypoints/
|-- data/
|   |-- deal_queue.json
|   |-- sent_deals.json
|   |-- melila_cache.json
|   |-- ml_session.json
|   `-- messages/
|-- logs/
|-- references/
`-- scripts/
    |-- deal_queue.py
    |-- deal_selection.py
    |-- dispatch_pending_deals.py
    |-- scan_deals.py
    |-- send_to_whatsapp.py
    |-- sender_worker.py
    `-- tests/
```

## Componentes ativos

- `core/domain/*`
  Regra de negocio pura.

- `core/application/*`
  Casos de uso de scan e sender.

- `core/ports/*`
  Contratos para desacoplamento.

- `core/adapters/*`
  Integracoes concretas com JSON, Playwright e afiliado.

- `core/entrypoints/*`
  CLI fina da arquitetura atual.

- `scripts/scan_deals.py`
  Compatibilidade de CLI para scan.

- `scripts/sender_worker.py`
  Compatibilidade de CLI para sender continuo.

- `scripts/dispatch_pending_deals.py`
  Compatibilidade de CLI para drenagem pontual.

- `run_scan.ps1`
  Wrapper operacional do scan no Windows.

- `run_sender.ps1`
  Wrapper operacional do sender continuo no Windows.

- `stop_sender.ps1`
  Encerramento do sender pelo lock file e sinal de parada.

## Estado persistido

- `data/deal_queue.json`
  Pools ativos e metadata de scan/sender.

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
- Os scripts antigos foram preservados para compatibilidade operacional.

## Melhorias futuras registradas

- Simplificar a composicao das dependencias em um bootstrap central.
- Encerramento mais gracioso do sender as 23:00 para reduzir ruido de driver/browser no log.
- Adicionar healthcheck ou watchdog do sender.
- Melhor observabilidade no scan com timestamp explicito de fim de rodada.
- Melhor observabilidade no sender com resumo por hora e total drenado da fila.
- Evoluir a persistencia de JSON para algo mais robusto se a concorrencia crescer.
