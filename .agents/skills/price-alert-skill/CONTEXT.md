# Context — price-alert-skill

## Sobre este documento
Este arquivo documenta o contexto completo do projeto e as decisões tomadas. Útil para continuidade em sessões futuras com outros agentes.

---

## O que é a skill
A `price-alert-skill` é um buscador de ofertas para marketplaces brasileiros (Amazon BR, Mercado Livre). Ela:
- Busca produtos por categoria em marketplaces
- Extrai preços atuais e descontos exibidos pelo próprio marketplace
- Gera mensagens formatadas para WhatsApp com ofertas encontradas
- **NÃO usa SQLite** — abordagem é scraping sob demanda

## Estrutura do repositório
```
.agents/skills/price-alert-skill/
├── SKILL.md                         # Documentação principal
├── CONTEXT.md                       # Este arquivo (contexto do projeto)
├── PLANO.md                         # Plano de execução e etapas
├── requirements.txt                 # Dependências Python
├── references/                      # Documentação de referência
│   ├── extraction-rules-amazon.md   # Regras de parsing Amazon
│   ├── extraction-rules-mercadolivre.md  # Regras de parsing ML
│   └── output-schema.md             # Schema de saída dos fetchers
└── scripts/
    ├── config.py                   # Configuração (tags de afiliado)
    ├── scrape_server.py             # Servidor Playwright (apenas Amazon)
    ├── scan_deals.py                # ★ SCRIPT PRINCIPAL — busca ofertas e gera mensagens
    ├── fetch_amazon_br.py           # Fetcher Amazon Brasil (extrai list_price + gera link afiliado)
    ├── fetch_ml_browser.py          # ★ Fetcher ML via agent-browser (links reais + afiliado)
    ├── fetch_mercadolivre_br.py     # Fetcher ML legado (HTML estático, fallback)
    ├── utils.py                     # Funções compartilhadas (emojis, formatação, templates, dedup)
    └── tests/                       # Testes unitários (96 testes)
        ├── test_utils.py            # Testes de utils
        ├── test_amazon.py           # Testes do parser Amazon (inclui build_affiliate_url)
        ├── test_mercadolivre.py     # Testes do parser ML legado
        └── test_ml_browser.py       # ★ Testes do fetcher agent-browser
```

## Dependências
- **Python 3.12+** (stdlib apenas)
- **fastapi** — servidor HTTP (apenas para Amazon)
- **uvicorn** — servidor ASGI (apenas para Amazon)
- **playwright** — browser headless com stealth (apenas para Amazon)
- **Chromium** — `playwright install chromium` (apenas para Amazon)
- **agent-browser** — CLI Rust para automação de browser (usado para ML)
- **Chrome for Testing** — `agent-browser install` (gerenciado pelo agent-browser)
- **Dependências de sistema**: `sudo apt install -y libnspr4 libnss3`

## Como usar (fluxo atual)

### 1. Instalar dependências
```bash
pip install fastapi uvicorn playwright
playwright install chromium
sudo apt install -y libnspr4 libnss3  # se necessário

# Agent-browser (para Mercado Livre — links reais)
npm install -g agent-browser
agent-browser install  # Baixa Chrome for Testing
```

### 2. Iniciar o servidor de scraping
```bash
cd .agents/skills/price-alert-skill/scripts
python3 scrape_server.py --port 3000
```

### 3. Buscar ofertas (script principal)
```bash
# Buscar ofertas de uma categoria (ML não precisa do scrape server)
python3 scan_deals.py "mouse gamer" --min-discount 10

# Buscar TODAS as categorias gamer
python3 scan_deals.py --all --min-discount 10

# Buscar apenas no Mercado Livre (sem precisar do scrape server)
python3 scan_deals.py "mouse gamer" --marketplaces mercadolivre_br --min-discount 5

# Opções
python3 scan_deals.py "ssd 2tb" --min-discount 5 --max-results 20
python3 scan_deals.py --all --marketplaces amazon_br --min-discount 15
```

### 4. Resultado
As mensagens são salvas em `data/messages/deals_YYYYMMDD_HHMMSS.json` e exibidas no terminal, prontas para copiar para WhatsApp.
Ofertas já enviadas em execuções anteriores são automaticamente filtradas via `data/sent_deals.json`.

### 5. Rodar testes
```bash
cd .agents/skills/price-alert-skill/scripts
python3 -m pytest tests/ -v
```

## Decisões tomadas

### 1. Substituição do Steel Browser
- **Problema**: Skill original dependia do Steel Browser (serviço externo pago).
- **Solução**: `scrape_server.py` com Playwright + Chromium local, replicando mesma API.
- **Stealth**: user-agent aleatório, viewport randomizado, injeção de JS anti-detecção.

### 2. Shopee — descartada
- Proteção anti-bot agressiva (interstitial, CAPTCHA).
- Login manual inviável (cookies expiram em 12h).
- **Decisão**: Focar apenas em Amazon BR e Mercado Livre.

### 3. Abordagem sem SQLite (decisão final)
- Repassar apenas o desconto que o marketplace exibe.
- Zero banco de dados, zero agendamento, zero manutenção.

### 4. Zoom — removido
- Scripts removidos: `fetch_zoom_history.py`, `link_zoom_product.py`, `enrich_with_zoom.py`.

### 5. Parser da Amazon atualizado
- Extrai `list_price` (preço anterior riscado) detectando segundo preço `a-offscreen` maior que o primeiro.

### 6. Parser do Mercado Livre reescrito
- HTML do ML mudou completamente (de `li.ui-search-layout__item` para `div.ui-search-result__wrapper`).
- Extrai preços dos `aria-label="Agora:"` e `aria-label="Antes:"`.
- URLs reais construídas a partir dos IDs MLB.

### 7. Código duplicado consolidado
- Funções compartilhadas em `scripts/utils.py` (emojis, formatação de preço, template de mensagem).

### 8. Formato das mensagens WhatsApp
- Preço antigo (Era:) exibido primeiro com strikethrough (`~~...~~`).
- Preço atual (Hoje:) exibido abaixo.
- Link do produto no final (WhatsApp gera preview com imagem automaticamente).

### 9. Deduplicação cross-session
- `data/sent_deals.json` armazena URLs de ofertas já processadas.
- Limpeza automática de ofertas com mais de 7 dias.
- Integrado no `scan_deals.py` — filtra antes de formatar mensagens.

### 10. Testes automatizados
- 79 testes unitários cobrindo utils, parser Amazon (incluindo geração de links afiliados) e parser ML (incluindo geração de links afiliados).
- Rodar com: `python3 -m pytest tests/ -v`

### 11. Links afiliados — Amazon BR (implementado)
- URLs da Amazon são automaticamente convertidas para links de afiliado usando `?tag=brunoentende-20`.
- Formato gerado: `https://www.amazon.com.br/dp/{ASIN}?tag=brunoentende-20`
- O ASIN é extraído do `data-asin` do card do produto. URLs longas com `ref=`, `linkCode`, `linkId` são sanitizadas para o formato limpo `/dp/{ASIN}?tag=XXX`.
- Tag configurável via variável de ambiente `AMAZON_AFFILIATE_TAG` (default: `brunoentende-20`) ou editando `scripts/config.py`.
- Implementação: função `build_affiliate_url()` em `fetch_amazon_br.py` + `config.py`.

### 12. Links afiliados — Mercado Livre (RESOLVIDO com agent-browser)
- **Problema original**: URLs construídas a partir do ID MLB (`produto.mercadolivre.com.br/MLB-{number}-_JM`) não eram confiáveis — alguns IDs geravam página 404.
- **Solução**: Implementado `fetch_ml_browser.py` que usa o **agent-browser** (CLI Rust) para renderizar a página com JavaScript e extrair os **links reais** do HTML renderizado.
- URLs reais extraídas: `https://www.mercadolivre.com.br/{slug-do-produto}/p/MLB{id}` (ex: `https://www.mercadolivre.com.br/mouse-gamer-redragon-cobra-rgb-preto-preto/p/MLB8752191`).
- Parâmetros de afiliado `matt_word=tb20240811145500` e `matt_tool=21915026` são anexados automaticamente.
- `scan_deals.py` agora usa `fetch_ml_browser.py` para ML em vez do servidor Playwright.
- O fetcher antigo `fetch_mercadolivre_br.py` (baseado em HTML estático) é mantido como fallback.

### 13. Mensagens WhatsApp — imagem removida do texto
- `format_deal_message()` não inclui mais `📷 Imagem do produto: {URL}` no texto.
- O campo `image_url` continua no dict do deal para uso futuro pelo `send_to_whatsapp.py` (Passo 2: enviar imagem como mídia com mensagem como legenda).

```
{emoji} OFERTA DO DIA 👇

{emoji} {NOME_PRODUTO}

~~📉 Era: R$ {PRECO_ANTERIOR}~~
🎯 Hoje: R$ {PRECO_ATUAL}
🔥 Desconto: {PERCENTUAL}% OFF

🛍️ Comprar aqui:
{LINK}

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

## Status dos marketplaces (10/04/2026)
| Marketplace | Status | Links afiliados | Observação |
|---|---|---|---|
| Amazon BR | Funcionando | Automático (`?tag=brunoentende-20`) | Extrai preço atual + preço anterior riscado |
| Mercado Livre | Funcionando ✅ | Automático (`?matt_word=...&matt_tool=...`) | Agent-browser extrai links reais com slug do HTML renderizado |
| Shopee BR | Descartada (por ora) | N/A | Proteção anti-bot inviável sem login — agent browser pode viabilizar |

## Dependências adicionais
- **agent-browser** — `npm install -g agent-browser` (CLI Rust para automação de browser)
- **Chrome for Testing** — `agent-browser install` (baixa Chrome automaticamente)
- Note: agent-browser não depende do Playwright. É um binário Rust independente que gerencia seu próprio Chrome.

## Comandos úteis
```bash
# Instalar agent-browser (primeira vez)
npm install -g agent-browser && agent-browser install

# Iniciar servidor de scraping (apenas para Amazon)
python3 scrape_server.py --port 3000

# Buscar ofertas de mouse gamer (ML usa agent-browser automaticamente)
python3 scan_deals.py "mouse gamer" --min-discount 10

# Buscar todas as categorias gamer
python3 scan_deals.py --all --min-discount 10

# Buscar com mais resultados
python3 scan_deals.py "ssd 2tb" --min-discount 5 --max-results 20
```
