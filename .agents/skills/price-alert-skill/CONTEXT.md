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
    ├── config.py                   # Configuração (tags de afiliado, credenciais login ML)
    ├── scrape_server.py             # Servidor Playwright (LEGADO — não mais necessário)
    ├── scan_deals.py                # ★ SCRIPT PRINCIPAL — busca ofertas e gera mensagens
    ├── fetch_amazon_br.py           # Fetcher Amazon Brasil (Playwright direto + link afiliado)
    ├── fetch_ml_browser.py          # ★ Fetcher ML via agent-browser (links reais)
    ├── fetch_mercadolivre_br.py     # Fetcher ML legado (HTML estático, fallback)
    ├── generate_melila_links.py     # ★ Gerador de links meli.la via painel de afiliados
    ├── utils.py                     # Funções compartilhadas (emojis, formatação, templates, dedup)
    └── tests/                       # Testes unitários (96 testes)
        ├── test_utils.py            # Testes de utils
        ├── test_amazon.py           # Testes do parser Amazon (inclui build_affiliate_url)
        ├── test_mercadolivre.py     # Testes do parser ML legado
        └── test_ml_browser.py       # ★ Testes do fetcher agent-browser
```

## Dependências
- **Python 3.12+** (stdlib apenas)
- **playwright** — browser headless com stealth (Amazon — uso direto, sem servidor)
- **Chromium** — `playwright install chromium` (Amazon)
- **agent-browser** — CLI Rust para automação de browser (usado para ML)
- **Chrome for Testing** — `agent-browser install` (gerenciado pelo agent-browser)
- **Dependências de sistema**: `sudo apt install -y libnspr4 libnss3`

## Como usar (fluxo atual)

### 1. Instalar dependências
```bash
pip install playwright
playwright install chromium
sudo apt install -y libnspr4 libnss3  # se necessário

# Agent-browser (para Mercado Livre — links reais)
npm install -g agent-browser
agent-browser install  # Baixa Chrome for Testing
```

### 2. Login no ML (primeira vez ou quando sessão expirar)
```bash
cd .agents/skills/price-alert-skill/scripts
ML_PROXY="http://200.174.198.32:8888" python3 generate_melila_links.py --login
# Resolve CAPTCHA/2FA manualmente no browser headed, depois pressiona Enter
```

### 3. Buscar ofertas (script principal)
```bash
# Buscar ofertas de uma categoria (Amazon + ML)
python3 scan_deals.py "mouse gamer" --min-discount 10

# Buscar TODAS as categorias gamer
python3 scan_deals.py --all --min-discount 10

# Buscar apenas no Mercado Livre
python3 scan_deals.py "mouse gamer" --marketplaces mercadolivre_br --min-discount 5
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

### 8. Formato das mensagens WhatsApp (atualizado 11/04/2026)
- `% OFF` aparece primeiro (mais impactante).
- `Antes:` sem strikethrough, linha separada.
- `Hoje:` preço atual na última linha de preço.
- Link do produto no final (WhatsApp gera preview com imagem automaticamente).
- Links ML usam formato `meli.la` (gerados via painel de afiliados) quando possível.

```
{emoji} OFERTA DO DIA 👇

{emoji} {NOME_PRODUTO}

🔥 {PERCENTUAL}% OFF
💰 Antes: R$ {PRECO_ANTERIOR}
🎯 Hoje: R$ {PRECO_ATUAL}

🛍️ Comprar aqui:
{LINK}

💸 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

### 9. Deduplicação cross-session
- `data/sent_deals.json` armazena URLs de ofertas já processadas.
- Limpeza automática de ofertas com mais de 7 dias.
- Integrado no `scan_deals.py` — filtra antes de formatar mensagens.

### 10. Testes automatizados
- 96 testes unitários cobrindo utils, parser Amazon (incluindo geração de links afiliados), parser ML (incluindo geração de links afiliados) e mensagens WhatsApp.
- Rodar com: `python3 -m pytest tests/ -v`

### 11. Links afiliados — Amazon BR (implementado)
- URLs da Amazon são automaticamente convertidas para links de afiliado usando `?tag=brunoentende-20`.
- Formato gerado: `https://www.amazon.com.br/dp/{ASIN}?tag=brunoentende-20`
- O ASIN é extraído do `data-asin` do card do produto. URLs longas com `ref=`, `linkCode`, `linkId` são sanitizadas para o formato limpo `/dp/{ASIN}?tag=XXX`.
- Tag configurável via variável de ambiente `AMAZON_AFFILIATE_TAG` (default: `brunoentende-20`) ou editando `scripts/config.py`.
- Implementação: função `build_affiliate_url()` em `fetch_amazon_br.py` + `config.py`.

### 12. Links afiliados — Mercado Livre (RESOLVIDO com agent-browser + meli.la)
- **Problema original**: URLs construídas a partir do ID MLB (`produto.mercadolivre.com.br/MLB-{number}-_JM`) não eram confiáveis — alguns IDs geravam página 404.
- **Solução**: Implementado `fetch_ml_browser.py` que usa o **agent-browser** (CLI Rust) para renderizar a página com JavaScript e extrair os **links reais** do HTML renderizado.
- URLs reais extraídas: `https://www.mercadolivre.com.br/{slug-do-produto}/p/MLB{id}` (ex: `https://www.mercadolivre.com.br/mouse-gamer-redragon-cobra-rgb-preto-preto/p/MLB8752191`).
- Links ML são **sempre** convertidos para `meli.la` via painel de afiliados — URLs longas com `matt_word`/`matt_tool` não são mais usadas.
- `scan_deals.py` agora usa `fetch_ml_browser.py` para ML em vez do servidor Playwright.
- O fetcher antigo `fetch_mercadolivre_br.py` (baseado em HTML estático) é mantido como fallback.

### 13. Mensagens WhatsApp — imagem removida do texto
- `format_deal_message()` não inclui mais `📷 Imagem do produto: {URL}` no texto.
- O campo `image_url` continua no dict do deal para uso futuro pelo `send_to_whatsapp.py` (Passo 2: enviar imagem como mídia com mensagem como legenda).

### 14. Links meli.la — geração via painel de afiliados (FUNCIONANDO via proxy)
- **Decisão**: Todos os links do Mercado Livre são convertidos para `meli.la` via painel de afiliados. URLs longas com `matt_word`/`matt_tool` foram removidas.
- **Bloqueio IP**: servidor bloqueado pelo ML CloudFront (403). Solução: usar proxy residencial brasileiro.
- **Gerador de Links**: em `mercadolivre.com.br/afiliados/linkbuilder`, aceita URLs no formato `https://www.mercadolivre.com.br/{slug}/p/MLB{id}`.
- **Geração em lote**: suportada! Campo "Insira 1 ou mais URLs separados por 1 linha" aceita múltiplas URLs separadas por newline.
- **Testado e funcionando**: geração individual e em lote de links meli.la via proxy.

### 15. Formato da mensagem atualizado (11/04/2026)
- Alterado de `~~📉 Era: R$ X~~` → `💰 Antes: R$ X` (sem strikethrough)
- Alterado de `🔥 Desconto: X% OFF` → `🔥 X% OFF` (simplificado)
- Ordem alterada: % OFF primeiro, depois Antes/Hoje
- Alinhado ao modelo de mensagem do cliente

### 16. Scrape server eliminado — Playwright direto (14/04/2026)
- **Problema**: `scrape_server.py` travava (hang) ao processar requisições da Amazon via FastAPI + Playwright async.
- **Causa provável**: conflito entre event loops do uvicorn e do Playwright async dentro do mesmo processo.
- **Solução**: `fetch_amazon_br.py` agora usa Playwright sync API diretamente, eliminando a necessidade do servidor.
- `scrape_server.py` mantido como legado mas não é mais necessário para o funcionamento.
- Dependências `fastapi` e `uvicorn` removidas dos requisitos.
- `scan_deals.py` atualizado: `run()` da Amazon não recebe mais `api_base` e `scrape_endpoint`.

### 17. Login ML via headed browser (14/04/2026)
- ML agora exige CAPTCHA (reCAPTCHA de imagem) + verificação 2FA (código por email) no login.
- Login automático não é mais viável — requer intervenção manual.
- `generate_melila_links.py --login` abre browser headed para login manual.
- Após login, a sessão do agent-browser é reutilizada para gerar links.
- Seletores de input atualizados para serem mais flexíveis (busca por "insira", "url", "link").

## Status dos marketplaces (11/04/2026)
| Marketplace | Status | Links afiliados | Observação |
|---|---|---|---|
| Amazon BR | Funcionando | Automático (`?tag=brunoentende-20`) | Extrai preço atual + preço anterior riscado |
| Mercado Livre | Funcionando (via proxy) | meli.la gerado automaticamente via painel | IP do servidor bloqueado pelo ML; usar proxy residencial |
| Shopee BR | Descartada (por ora) | N/A | Proteção anti-bot inviável sem login — agent browser pode viabilizar |

## Dependências adicionais
- **agent-browser** — `npm install -g agent-browser` (CLI Rust para automação de browser)
- **Chrome for Testing** — `agent-browser install` (baixa Chrome automaticamente)
- **Proxy residencial** — IP do servidor é bloqueado pelo ML CloudFront. Usar variável de ambiente `ML_PROXY` ou flag `--proxy`
- Note: agent-browser não depende do Playwright. É um binário Rust independente que gerencia seu próprio Chrome.

## Comandos úteis
```bash
# Instalar agent-browser (primeira vez)
npm install -g agent-browser && agent-browser install

# Login manual no ML (primeira vez ou sessão expirou)
ML_PROXY="http://200.174.198.32:8888" python3 generate_melila_links.py --login

# Buscar ofertas (Amazon + ML) — não precisa mais do scrape server!
python3 scan_deals.py "mouse gamer" --min-discount 10

# Buscar todas as categorias gamer
python3 scan_deals.py --all --min-discount 10

# Buscar com mais resultados
python3 scan_deals.py "ssd 2tb" --min-discount 5 --max-results 20

# Gerar meli.la manualmente (com proxy)
ML_PROXY="http://200.174.198.32:8888" python3 generate_melila_links.py --urls "https://www.mercadolivre.com.br/mouse-gamer/p/MLB123"

# Rodar testes
python3 -m pytest tests/ -v
```
