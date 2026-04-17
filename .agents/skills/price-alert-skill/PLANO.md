# PLANO — price-alert-skill

## Objetivo

Buscar ofertas em marketplaces brasileiros, gerar links de afiliado, montar mensagens para WhatsApp e, quando desejado, enviar essas mensagens automaticamente para um grupo.

## Estado atual

O fluxo principal já existe e é este:

1. `scripts/scan_deals.py` faz a busca e a deduplicação.
2. Amazon BR é coletada por `scripts/fetch_amazon_br.py`.
3. Mercado Livre é coletado por `scripts/fetch_ml_browser.py`.
4. Links do Mercado Livre podem virar `meli.la` com `scripts/generate_melila_links.py`.
5. Mensagens são formatadas por `scripts/utils.py`.
6. O envio opcional para WhatsApp é feito por `scripts/send_to_whatsapp.py`.

Não é necessário subir servidor auxiliar para esse fluxo.

## Plano operacional

### 1. Preparação

```bash
pip install -r requirements.txt
playwright install chromium
```

No Ubuntu/WSL, se o Chromium pedir bibliotecas compartilhadas:

```bash
sudo apt install -y libnspr4 libnss3
```

### 2. Configuração

Crie o `.env` a partir do `.env.example` e preencha pelo menos:

```env
AMAZON_AFFILIATE_TAG=sua-tag
WHATSAPP_GROUP=Nome do grupo padrão
```

`WHATSAPP_GROUP` passou a ser o grupo padrão do fluxo end-to-end. Quando necessário, o CLI ainda pode sobrescrever esse valor com `--whatsapp-group` ou `--group`.

### 3. Login inicial do Mercado Livre

```bash
python3 scripts/generate_melila_links.py --login
```

Esse passo salva a sessão em `data/ml_session.json`.

### 4. Login inicial do WhatsApp

```bash
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp --headed
```

Esse passo usa `WHATSAPP_GROUP` do `.env` como grupo padrão e salva a sessão em `data/whatsapp_session/`.

### 5. Execução diária

```bash
python3 scripts/scan_deals.py --all --min-discount 10
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp
```

### 6. Sobrescrita pontual do grupo

```bash
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp --whatsapp-group "Grupo de Teste"
python3 scripts/send_to_whatsapp.py --deals data/messages/deals_YYYYMMDD_HHMMSS.json --group "Grupo de Teste"
```

## Arquivos importantes

- `data/sent_deals.json` — deduplicação entre execuções
- `data/melila_cache.json` — cache de links `meli.la`
- `data/ml_session.json` — sessão do Mercado Livre afiliados
- `data/whatsapp_session/` — sessão do WhatsApp Web
- `data/messages/` — saída das mensagens geradas

## O que não faz parte do plano atual

- Iniciar `scrape_server.py`
- Depender de `agent-browser`
- Manter contagens fixas de testes ou histórico detalhado de commits nesta documentação
- Manter instruções de fluxos já removidos do caminho principal

## Próximos ajustes quando houver necessidade

- Atualizar seletores caso Amazon, Mercado Livre ou WhatsApp Web mudem
- Revalidar a sessão do Mercado Livre quando `meli.la` parar de ser gerado
- Revalidar a sessão do WhatsApp quando o QR voltar a aparecer
