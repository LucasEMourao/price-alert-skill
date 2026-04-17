---
name: price-alert-monitor
description: Busque ofertas na Amazon BR e no Mercado Livre, gere links de afiliado e monte mensagens prontas para WhatsApp.
---

# Price Alert Monitor

Skill para busca sob demanda de ofertas em marketplaces brasileiros.

## O que a skill faz

- Busca ofertas na Amazon BR e no Mercado Livre
- Extrai preço atual e preço anterior exibido pelo marketplace
- Filtra ofertas por desconto mínimo
- Gera links de afiliado para Amazon BR e links `meli.la` para Mercado Livre
- Formata mensagens prontas para WhatsApp
- Pode enviar automaticamente as ofertas pelo WhatsApp Web

## Fluxo atual

1. Instale as dependências Python e o Chromium do Playwright.
2. Configure o `.env`.
3. Na primeira vez, faça o login manual do Mercado Livre com `python3 scripts/generate_melila_links.py --login`.
4. Se for usar envio automático, faça o login inicial do WhatsApp com `python3 scripts/scan_deals.py --all --send-whatsapp --headed`.
5. Rode `scripts/scan_deals.py` com uma query específica ou com `--all`.
6. As mensagens são exibidas no terminal e salvas em `data/messages/deals_*.json`.
7. Quando `--send-whatsapp` for usado, o grupo padrão vem de `WHATSAPP_GROUP` no `.env`; `--whatsapp-group` continua disponível como sobrescrita manual.

## Scripts principais

- `scripts/scan_deals.py` — fluxo principal de busca, filtro, deduplicação, geração de mensagens e envio opcional para WhatsApp
- `scripts/fetch_amazon_br.py` — scraping da Amazon BR com Playwright e geração de link afiliado
- `scripts/fetch_ml_browser.py` — scraping do Mercado Livre com Playwright e extração via DOM renderizado
- `scripts/generate_melila_links.py` — geração de links `meli.la` via painel de afiliados do Mercado Livre
- `scripts/send_to_whatsapp.py` — envio automático de imagem + legenda no WhatsApp Web
- `scripts/utils.py` — utilitários compartilhados de desconto, deduplicação e formatação
- `scripts/config.py` — leitura do `.env` e resolução de configurações compartilhadas
- `scripts/scrape_server.py` — legado, mantido apenas para referência; não faz parte do fluxo atual
- `scripts/fetch_mercadolivre_br.py` — parser legado do Mercado Livre; não é o caminho principal

## Variáveis de ambiente

- `AMAZON_AFFILIATE_TAG` — tag usada nos links afiliados da Amazon BR
- `WHATSAPP_GROUP` — grupo padrão usado por `scan_deals.py` e `send_to_whatsapp.py`
- `ML_PROXY` — proxy opcional para cenários em que o painel de afiliados do Mercado Livre bloquear o IP
- `ML_AFFILIATE_EMAIL` e `ML_AFFILIATE_PASSWORD` — mantidas no `.env.example` para referência, embora o login atual seja manual no navegador

## Instalação

```bash
pip install -r requirements.txt
playwright install chromium
sudo apt install -y libnspr4 libnss3  # se o Ubuntu/WSL pedir libs extras do Chromium
```

## Comandos úteis

```bash
# Login manual no Mercado Livre afiliados
python3 scripts/generate_melila_links.py --login

# Buscar uma categoria
python3 scripts/scan_deals.py "mouse gamer" --min-discount 10

# Buscar todas as categorias monitoradas
python3 scripts/scan_deals.py --all --min-discount 10

# Enviar usando o grupo padrão do .env
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp

# Sobrescrever o grupo do .env apenas nesta execução
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp --whatsapp-group "Grupo de Teste"

# Login inicial do WhatsApp via QR code
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp --headed

# Usar o sender diretamente com o grupo do .env
python3 scripts/send_to_whatsapp.py --deals data/messages/deals_YYYYMMDD_HHMMSS.json
```

## Categorias monitoradas por `--all`

- `mouse gamer`
- `teclado mecanico gamer`
- `headset gamer`
- `monitor gamer`
- `ssd 2tb`
- `memoria ram ddr5`
- `placa de video rtx`
- `notebook gamer`
- `gabinete gamer`
- `fonte gamer`
- `cooler gamer`
- `mousepad gamer`

## Formato da mensagem

```text
{emoji} OFERTA DO DIA 👇

{emoji} {NOME_DO_PRODUTO}

🔥 {PERCENTUAL}% OFF
💰 Antes: ~R$ {PRECO_ANTERIOR}~
🎯 Hoje: R$ {PRECO_ATUAL}

🛍️ Comprar aqui:
{LINK}

💸 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

Quando não houver preço anterior exibido, a mensagem sai apenas com a linha `🎯 Hoje`.

## Observações operacionais

- A deduplicação entre execuções usa `data/sent_deals.json`.
- O cache de links `meli.la` usa `data/melila_cache.json`.
- A sessão do Mercado Livre fica em `data/ml_session.json`.
- A sessão do WhatsApp Web fica em `data/whatsapp_session/`.
- O fluxo depende da estrutura atual dos marketplaces e do WhatsApp Web; mudanças de seletor podem exigir manutenção.
