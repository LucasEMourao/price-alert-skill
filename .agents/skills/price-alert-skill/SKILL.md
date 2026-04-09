---
name: price-alert-monitor
description: Busque ofertas em marketplaces brasileiros (Amazon BR, Mercado Livre) e gere mensagens formatadas para WhatsApp. Use esta skill quando o usuario quiser buscar descontos por categoria ou varrer todas as categorias de uma vez.
---

# Price Alert Monitor

Skill para busca sob demanda de ofertas em marketplaces brasileiros.

- Busca resultados na Amazon BR e Mercado Livre
- Extrai preco atual e preco anterior riscado (quando exibido pelo marketplace)
- Filtra produtos com desconto acima de um limite minimo
- **Gera links de afiliado automaticamente para Amazon BR** (`?tag=brunoentende-20`) **e Mercado Livre** (`?matt_word=...&matt_tool=...`)
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

- `scripts/config.py` — Configuracao (tags de afiliado, constantes)
- `scripts/scrape_server.py` — Servidor Playwright com stealth (substitui Steel Browser)
- `scripts/scan_deals.py` — Script principal: busca ofertas e gera mensagens WhatsApp
- `scripts/fetch_amazon_br.py` — Fetcher Amazon BR (extrai preco, gera link afiliado)
- `scripts/fetch_mercadolivre_br.py` — Fetcher Mercado Livre (extrai preco, gera link afiliado)
- `scripts/utils.py` — Funcoes compartilhadas (emojis, formatacao de preco, template de mensagem)

## Comandos

```bash
# Iniciar servidor de scraping
python3 scripts/scrape_server.py --port 3000

# Buscar ofertas de uma categoria
python3 scripts/scan_deals.py "mouse gamer" --min-discount 10

# Varrer todas as categorias gamer
python3 scripts/scan_deals.py --all --min-discount 10

# Buscar com mais resultados
python3 scripts/scan_deals.py "ssd 2tb" --min-discount 5 --max-results 20

# Buscar apenas na Amazon
python3 scripts/scan_deals.py --all --marketplaces amazon_br --min-discount 15
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

~~📉 Era: R$ {PRECO_ANTERIOR}~~
🎯 Hoje: R$ {PRECO_ATUAL}
🔥 Desconto: {PERCENTUAL}% OFF

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
- **fastapi**, **uvicorn**, **playwright**
- **Chromium**: `playwright install chromium`
- **Sistema**: `sudo apt install -y libnspr4 libnss3`

## Guardrails

- O servidor de scraping (`scripts/scrape_server.py`) deve estar rodando em `http://localhost:3000`.
- Amazon BR gera links de afiliado automaticamente com tag `brunoentende-20` (configuravel via env var `AMAZON_AFFILIATE_TAG`).
- Mercado Livre gera links de afiliado automaticamente com `matt_word` e `matt_tool` (configuravel via env vars `ML_MATT_WORD` e `ML_MATT_TOOL`). URLs usam formato `www.mercadolivre.com.br/p/MLB_ID`.
- Shopee BR nao e suportada (protecao anti-bot inviabiliza uso).
- Confiar nos descontos exibidos pelo proprio marketplace — nao ha validacao externa.
- Se nao houver descontos relevantes, responder: `Sem descontos encontrados no momento.`
