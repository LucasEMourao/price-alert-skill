---
name: price-alert-monitor
description: Busque ofertas em marketplaces brasileiros (Amazon BR, Mercado Livre) e gere mensagens formatadas para WhatsApp. Use esta skill quando o usuario quiser buscar descontos por categoria ou varrer todas as categorias de uma vez.
---

# Price Alert Monitor

Skill para busca sob demanda de ofertas em marketplaces brasileiros.

- Busca resultados na Amazon BR e Mercado Livre
- Extrai preco atual e preco anterior riscado (quando exibido pelo marketplace)
- Filtra produtos com desconto acima de um limite minimo
- **Gera links de afiliado automaticamente para Amazon BR** (`?tag=brunoentende-20`) **e Mercado Livre** (links `meli.la` via painel de afiliados)
- Gera mensagens formatadas para WhatsApp prontas para copiar/colar

## Comportamento Padrao

- Sempre tente executar o fluxo, nao responda apenas com comandos para o usuario rodar.
- Quando o usuario pedir para buscar ofertas, rode `scan_deals.py` diretamente.
- Responda em PT-BR por padrao.

## Quando Usar

- O usuario quer buscar ofertas em uma categoria especifica.
- O usuario quer varrer todas as categorias de uma vez.
- O usuario quer mensagens prontas para WhatsApp com ofertas encontradas.

## Fluxo

1. Inicie o servidor de scraping: `python3 scripts/scrape_server.py --port 3000`
2. Rode `scripts/scan_deals.py` com a query desejada ou `--all` para todas as categorias.
3. As mensagens sao exibidas no terminal e salvas em `data/messages/deals_*.json`.

## Scripts Principais

- `scripts/config.py` — Configuracao (tags de afiliado, credenciais de login ML)
- `scripts/scrape_server.py` — Servidor Playwright com stealth (usado pela Amazon)
- `scripts/scan_deals.py` — Script principal: busca ofertas e gera mensagens WhatsApp
- `scripts/fetch_amazon_br.py` — Fetcher Amazon BR (extrai preco, gera link afiliado)
- `scripts/fetch_ml_browser.py` — Fetcher Mercado Livre via agent-browser (links reais, gera link afiliado)
- `scripts/fetch_mercadolivre_br.py` — Fetcher ML legado (HTML estático, mantido como fallback)
- `scripts/generate_melila_links.py` — Gerador de links meli.la via painel de afiliados do ML
- `scripts/utils.py` — Funcoes compartilhadas (emojis, formatacao de preco, template de mensagem)

## Comandos

```bash
# Instalar dependências (primeira vez)
pip install fastapi uvicorn playwright
playwright install chromium
npm install -g agent-browser
agent-browser install

# Iniciar servidor de scraping (necessário apenas para Amazon)
python3 scripts/scrape_server.py --port 3000

# Buscar ofertas de uma categoria (ML usa agent-browser, Amazon usa scrape server)
python3 scripts/scan_deals.py "mouse gamer" --min-discount 10

# Varrer todas as categorias gamer
python3 scripts/scan_deals.py --all --min-discount 10

# Buscar apenas no Mercado Livre (não precisa do scrape server)
python3 scripts/scan_deals.py "mouse gamer" --marketplaces mercadolivre_br --min-discount 5

# Buscar apenas na Amazon (requer scrape server rodando)
python3 scripts/scan_deals.py --all --marketplaces amazon_br --min-discount 15

# Buscar SEM geração de meli.la (usa URLs longas com matt_word/matt_tool)
python3 scripts/scan_deals.py "mouse gamer" --no-melila --min-discount 10

# Gerar meli.la manualmente para URLs específicas
python3 scripts/generate_melila_links.py "https://produto.mercadolivre.com.br/MLB-XXXXX"
```

## Categorias Monitoradas

| Categoria | Query |
|---|---|
| Mouse | "mouse gamer" |
| Teclado | "teclado mecanico gamer" |
| Headset | "headset gamer" |
| Monitor | "monitor gamer" |
| SSD | "ssd 2tb" |
| Memoria RAM | "memoria ram ddr5" |
| Placa de video | "placa de video rtx" |
| Notebook | "notebook gamer" |
| Gabinete | "gabinete gamer" |
| Fonte | "fonte gamer" |
| Cooler | "cooler gamer" |
| Mousepad | "mousepad gamer" |

## Formato da Mensagem WhatsApp

**Com desconto:**
```
{emoji} OFERTA DO DIA 👇

{emoji} {NOME_DO_PRODUTO}

🔥 {PERCENTUAL}% OFF
💰 Antes: R$ {PRECO_ANTERIOR}
🎯 Hoje: R$ {PRECO_ATUAL}

🛍️ Comprar aqui:
{LINK}

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

**Sem desconto exibido:**
```
{emoji} OFERTA DO DIA 👇

{emoji} {NOME_DO_PRODUTO}

🎯 Hoje: R$ {PRECO_ATUAL}

🛍️ Comprar aqui:
{LINK}

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

O link do produto no final da mensagem gera automaticamente um preview com imagem no WhatsApp.

## Dependencias

- **Python 3.12+**
- **fastapi**, **uvicorn**, **playwright** (apenas para Amazon)
- **Chromium** (Playwright): `playwright install chromium`
- **agent-browser**: `npm install -g agent-browser && agent-browser install`
- **Sistema**: `sudo apt install -y libnspr4 libnss3`
- **Proxy residencial** (para ML): IP do servidor e bloqueado pelo ML CloudFront. Variavel de ambiente `ML_PROXY` ou flag `--proxy`.

## Guardrails

- O servidor de scraping (`scripts/scrape_server.py`) deve estar rodando apenas para Amazon (`http://localhost:3000`). **ML usa agent-browser e nao depende do servidor.**
- Amazon BR gera links de afiliado automaticamente com tag `brunoentende-20` (configuravel via env var `AMAZON_AFFILIATE_TAG`). **Funcionando e testado.**
- Mercado Livre gera links `meli.la` automaticamente via painel de afiliados (agent-browser + proxy). **Funcionando e testado.**
- Para ML, usar proxy residencial brasileiro via `ML_PROXY` (env var) ou `--proxy` (flag). Exemplo: `ML_PROXY="http://200.174.198.32:8888"`.
- Shopee BR nao e suportada por enquanto (agent browser pode viabilizar no futuro).
- Confiar nos descontos exibidos pelo proprio marketplace — nao ha validacao externa.
- Se nao houver descontos relevantes, responder: `Sem descontos encontrados no momento.`
