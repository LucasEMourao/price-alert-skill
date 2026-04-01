# Context — price-alert-skill

## Sobre este documento
Este arquivo documenta o contexto completo do projeto e as decisões tomadas. Útil para continuidade em sessões futuras com outros agentes.

---

## O que é a skill
A `price-alert-skill` é um monitor de ofertas para marketplaces brasileiros (Amazon BR, Mercado Livre). Ela:
- Busca produtos por categoria em marketplaces
- Extrai preços atuais e descontos exibidos pelo próprio marketplace
- Gera mensagens formatadas para WhatsApp com ofertas encontradas
- **NÃO usa SQLite** — a abordagem atual repassa apenas o que o marketplace exibe

## Estrutura do repositório
```
.agents/skills/price-alert-skill/
├── SKILL.md                         # Documentação principal
├── CONTEXT.md                       # Este arquivo (contexto do projeto)
├── PLANO.md                         # Plano de execução e etapas
├── requirements.txt                 # Dependências Python
├── references/                      # Documentação de referência
│   ├── extraction-rules-*.md        # Regras de parsing por marketplace
│   ├── watchlist-gamer.json         # Config de watchlists gamer
│   └── *.example.json               # Exemplos de configuração
└── scripts/
    ├── scrape_server.py             # Servidor Playwright (substitui Steel Browser)
    ├── scan_deals.py                # ★ SCRIPT PRINCIPAL — busca ofertas e gera mensagens
    ├── fetch_amazon_br.py           # Fetcher Amazon Brasil (extrai list_price)
    ├── fetch_mercadolivre_br.py     # Fetcher Mercado Livre
    ├── fetch_shopee_br.py           # Fetcher Shopee Brasil (parcial)
    ├── format_deal_messages.py      # Formata deals como WhatsApp
    ├── detect_deals.py              # Detecta deals por histórico SQLite (legado)
    ├── scheduler.py                 # Agendador com SQLite (legado)
    ├── monitor_query.py             # Monitora query com SQLite (legado)
    ├── onboard_watchlist.py         # Cria watchlists no SQLite (legado)
    └── ... (outros scripts legados)
```

**Scripts ativos:** `scrape_server.py`, `scan_deals.py`, `fetch_amazon_br.py`, `fetch_mercadolivre_br.py`
**Scripts legados:** Todos os que usam SQLite (`monitor_query.py`, `scheduler.py`, `detect_deals.py`, etc.)

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
- **Problema inicial**: Usar SQLite para histórico de preços e calcular média/mediana.
- **Análise**: Para detectar "promoção real", seria necessário coletar dados por semanas/meses.
- **Decisão do usuário**: Repassar apenas o desconto que o marketplace exibe. Se o site mostra "de R$ 2.000 por R$ 1.500", essa é a informação oficial — não é necessário validar se é "promoção real".
- **Vantagens**: Zero banco de dados, zero agendamento, zero manutenção. Scraping sob demanda.
- **Limitação aceita**: Descontos exibidos pelo marketplace podem ser inflados artificialmente, mas a responsabilidade é do marketplace, não nossa.

### 4. Parser da Amazon atualizado
- Parser original não extraía `list_price` (preço anterior riscado).
- Ajustado para detectar segundo preço `a-offscreen` maior que o primeiro = preço original.
- Resultado: 90% dos produtos agora retornam desconto exibido.

### 5. Formato das mensagens WhatsApp
Definido pelo usuário com base em exemplo real:
```
{emoji} OFERTA DO DIA 👇

{emoji} {NOME_PRODUTO}

🎯 Hoje: R$ {PRECO_ATUAL}
📉 Era: R$ {PRECO_ANTERIOR}
🔥 Desconto: {PERCENTUAL}% OFF

🛍️ Comprar aqui:
{LINK}

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

## Status dos marketplaces (01/04/2026)
| Marketplace | Status | Observação |
|---|---|---|
| Amazon BR | Funcionando | Extrai preço atual + preço anterior riscado |
| Mercado Livre | Funcionando | Extrai preço atual (preço anterior pendente) |
| Shopee BR | Descartada | Proteção anti-bot inviabiliza uso |

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

## Possíveis melhorias futuras
- **Mercado Livre**: Ajustar parser para extrair preço anterior riscado (como feito na Amazon)
- **Integração WhatsApp**: Enviar mensagens automaticamente via API ou pywhatkit
- **Filtro por preço mínimo**: Ignorar produtos muito baratos (acessórios genéricos)
- **Deduplicação**: Evitar repetir ofertas já enviadas anteriormente
