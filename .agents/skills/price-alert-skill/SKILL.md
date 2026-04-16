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

1. (Primeira vez) Login no ML: `python3 scripts/generate_melila_links.py --login`
2. (Primeira vez WhatsApp) Login via QR code: `python3 scripts/scan_deals.py --send-whatsapp --whatsapp-group "Grupo" --headed`
3. Rode `scripts/scan_deals.py` com a query desejada ou `--all` para todas as categorias.
4. As mensagens sao exibidas no terminal e salvas em `data/messages/deals_*.json`.
5. (Opcional) Envie automaticamente para WhatsApp com `--send-whatsapp`.

## Scripts Principais

- `scripts/config.py` — Configuracao (tags de afiliado, credenciais de login ML)
- `scripts/scrape_server.py` — LEGADO — Servidor Playwright (nao mais necessario)
- `scripts/scan_deals.py` — Script principal: busca ofertas e gera mensagens WhatsApp
- `scripts/fetch_amazon_br.py` — Fetcher Amazon BR (Playwright direto + link afiliado)
- `scripts/fetch_ml_browser.py` — Fetcher Mercado Livre via agent-browser (links reais)
- `scripts/fetch_mercadolivre_br.py` — Fetcher ML legado (HTML estático, mantido como fallback)
- `scripts/generate_melila_links.py` — Gerador de links meli.la via painel de afiliados do ML
- `scripts/send_to_whatsapp.py` — Envio automático para WhatsApp via Playwright (★ NOVO)
- `scripts/utils.py` — Funcoes compartilhadas (emojis, formatacao de preco, template de mensagem)

## Comandos

```bash
# Instalar dependências (primeira vez)
pip install playwright
playwright install chromium
npm install -g agent-browser
agent-browser install

# Login manual no ML (primeira vez ou sessão expirou)
python3 scripts/generate_melila_links.py --login

# Buscar ofertas de uma categoria (Amazon + ML)
python3 scripts/scan_deals.py "mouse gamer" --min-discount 10

# Varrer todas as categorias gamer
python3 scripts/scan_deals.py --all --min-discount 10

# Buscar apenas no Mercado Livre
python3 scripts/scan_deals.py "mouse gamer" --marketplaces mercadolivre_br --min-discount 5

# Buscar apenas na Amazon
python3 scripts/scan_deals.py --all --marketplaces amazon_br --min-discount 15

# Gerar meli.la manualmente para URLs específicas
python3 scripts/generate_melila_links.py "https://produto.mercadolivre.com.br/MLB-XXXXX"

# Enviar ofertas para WhatsApp (primeira vez — headed para QR)
python3 scripts/scan_deals.py "mouse gamer" --min-discount 10 --send-whatsapp --whatsapp-group "Grupo de Ofertas" --headed

# Enviar ofertas após sessão inicial
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp --whatsapp-group "Grupo de Ofertas"

# Usar script de envio diretamente
python3 scripts/send_to_whatsapp.py --group "Grupo de Ofertas" --deals data/messages/deals_*.json
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
💰 Antes: ~R$ {PRECO_ANTERIOR}~
🎯 Hoje: R$ {PRECO_ATUAL}

🛍️ Comprar aqui:
{LINK}

💸 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

**Sem desconto exibido:**
```
{emoji} OFERTA DO DIA 👇

{emoji} {NOME_DO_PRODUTO}

🎯 Hoje: R$ {PRECO_ATUAL}

🛍️ Comprar aqui:
{LINK}

💸 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

O link do produto no final da mensagem gera automaticamente um preview com imagem no WhatsApp.

**Envio com imagem + legenda:** O script `send_to_whatsapp.py` envia automaticamente a imagem do produto com a mensagem formatada como legenda, incluindo o link de afiliado.

## Dependencias

- **Python 3.12+**
- **playwright** (Amazon + WhatsApp — uso direto, sem servidor)
- **Chromium** (Playwright): `playwright install chromium`
- **requests** (download de imagens para WhatsApp)
- **agent-browser**: `npm install -g agent-browser && agent-browser install`
- **Sistema**: `sudo apt install -y libnspr4 libnss3`
- **Proxy residencial** (para ML): IP do servidor e bloqueado pelo ML CloudFront. Variavel de ambiente `ML_PROXY` ou flag `--proxy`.

## Guardrails

- **Amazon BR** usa Playwright direto (sem servidor). Gera links de afiliado automaticamente com tag `brunoentende-20` (configuravel via env var `AMAZON_AFFILIATE_TAG`). **Funcionando e testado.**
- **Mercado Livre** gera links `meli.la` automaticamente via painel de afiliados (agent-browser + proxy). **Requer login manual** (`--login`) para resolver CAPTCHA/2FA. **Funcionando e testado.**
- Para ML, usar proxy residencial brasileiro via `ML_PROXY` (env var) ou `--proxy` (flag). Exemplo: `ML_PROXY="http://200.174.198.32:8888"`.
- **WhatsApp Web** envio automático via Playwright. **Requer login manual** na primeira vez (`--headed`). Sessão persiste em `data/whatsapp_session/chrome_profile/` (perfil completo do Chrome com IndexedDB). **Funcionando e testado.**
  - Envia imagem do produto + legenda formatada (com preço antigo riscado via `~`)
  - Delay de 5s entre mensagens para evitar rate limit
  - Sincronização de 5s antes de fechar o navegador
- Shopee BR nao e suportada por enquanto (agent browser pode viabilizar no futuro).
- Confiar nos descontos exibidos pelo proprio marketplace — nao ha validacao externa.
- Se nao houver descontos relevantes, responder: `Sem descontos encontrados no momento.`
