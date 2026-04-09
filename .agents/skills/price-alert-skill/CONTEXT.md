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
    ├── scrape_server.py             # Servidor Playwright (substitui Steel Browser)
    ├── scan_deals.py                # ★ SCRIPT PRINCIPAL — busca ofertas e gera mensagens
    ├── fetch_amazon_br.py           # Fetcher Amazon Brasil (extrai list_price + gera link afiliado)
    ├── fetch_mercadolivre_br.py     # Fetcher Mercado Livre (extrai list_price + gera link afiliado)
    ├── utils.py                     # Funções compartilhadas (emojis, formatação, templates, dedup)
    └── tests/                       # Testes unitários
        ├── test_utils.py            # Testes de utils
        ├── test_amazon.py           # Testes do parser Amazon (inclui build_affiliate_url)
        └── test_mercadolivre.py     # Testes do parser ML (inclui build_affiliate_url)
```

## Dependências
- **Python 3.12+** (stdlib apenas)
- **fastapi** — servidor HTTP
- **uvicorn** — servidor ASGI
- **playwright** — browser headless com stealth
- **Chromium** — `playwright install chromium`
- **Dependências de sistema**: `sudo apt install -y libnspr4 libnss3`

## Como usar (fluxo atual)

### 1. Instalar dependências
```bash
pip install fastapi uvicorn playwright
playwright install chromium
sudo apt install -y libnspr4 libnss3  # se necessário
```

### 2. Iniciar o servidor de scraping
```bash
cd .agents/skills/price-alert-skill/scripts
python3 scrape_server.py --port 3000
```

### 3. Buscar ofertas (script principal)
```bash
# Buscar ofertas de uma categoria
python3 scan_deals.py "mouse gamer" --min-discount 10

# Buscar TODAS as categorias gamer
python3 scan_deals.py --all --min-discount 10

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

### 12. Links afiliados — Mercado Livre (implementado)
- URLs do Mercado Livre usam formato `produto.mercadolivre.com.br/MLB-{number}-_JM` com hífen obrigatório entre prefixo e número.
- O formato antigo `produto.mercadolivre.com.br/MLB5351289630` (sem hífen) retorna 404.
- O formato `/p/MLB_ID` em `www.mercadolivre.com.br` também retorna 404.
- Parâmetros de afiliado `matt_word` e `matt_tool` são anexados via query string.
- Formato gerado: `https://produto.mercadolivre.com.br/MLB-5351289630-_JM?matt_word=tb20240811145500&matt_tool=21915026`
- Parâmetros configuráveis via variáveis de ambiente `ML_MATT_WORD` e `ML_MATT_TOOL` em `config.py`.
- Implementação: função `build_affiliate_url()` em `fetch_mercadolivre_br.py`.

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

## Status dos marketplaces (09/04/2026)
| Marketplace | Status | Links afiliados | Observação |
|---|---|---|---|
| Amazon BR | Funcionando | Automático (`?tag=brunoentende-20`) | Extrai preço atual + preço anterior riscado |
| Mercado Livre | Funcionando | Automático (`?matt_word=...&matt_tool=...`) | Extrai preço atual + preço anterior riscado |
| Shopee BR | Descartada | N/A | Proteção anti-bot inviabiliza uso |

## Comandos úteis
```bash
# Iniciar servidor de scraping
python3 scrape_server.py --port 3000

# Buscar ofertas de mouse gamer
python3 scan_deals.py "mouse gamer" --min-discount 10

# Buscar todas as categorias gamer
python3 scan_deals.py --all --min-discount 10

# Buscar com mais resultados
python3 scan_deals.py "ssd 2tb" --min-discount 5 --max-results 20
```
