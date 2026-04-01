# Context — price-alert-skill

## Sobre este documento
Este arquivo documenta o contexto completo do projeto e as decisões tomadas. Útil para continuidade em sessões futuras com outros agentes.

---

## O que é a skill
A `price-alert-skill` é um monitor de preços automático para marketplaces brasileiros (Amazon BR, Mercado Livre, Shopee BR). Ela:
- Busca produtos por categoria ou links específicos
- Armazena histórico de preços em SQLite
- Gera alertas de ofertas deduplicados, prontos para WhatsApp
- Suporta atualizações recorrentes a cada N minutos
- Enriquece dados com baseline do Zoom.com.br

## Estrutura do repositório
```
.agents/skills/price-alert-skill/
├── SKILL.md                    # Documentação principal da skill
├── requirements.txt            # Dependências Python
├── references/                 # Documentação de referência
│   ├── extraction-rules-*.md   # Regras de parsing por marketplace
│   ├── output-schema.md        # Schema de saída dos fetchers
│   ├── storage-layout.md       # Schema do banco SQLite
│   └── *.example.json          # Exemplos de configuração
└── scripts/
    ├── scrape_server.py        # Servidor Playwright (substitui Steel Browser)
    ├── fetch_amazon_br.py      # Fetcher Amazon Brasil
    ├── fetch_mercadolivre_br.py # Fetcher Mercado Livre
    ├── fetch_shopee_br.py      # Fetcher Shopee Brasil
    ├── onboard_watchlist.py    # Cria watchlists a partir de JSON
    ├── update_watchlist.py     # Atualiza watchlists pendentes
    ├── refresh_watchlist_messages.py # Gera mensagens WhatsApp
    ├── generate_alert_payloads.py    # Gera payloads de alerta
    ├── format_whatsapp_alerts.py     # Formata mensagens WhatsApp
    ├── run_all_monitors.py     # Executa todos os monitores
    ├── monitor_query.py        # Monitora uma query específica
    ├── enrich_with_zoom.py     # Enriquece com dados do Zoom
    ├── fetch_zoom_history.py   # Busca histórico Zoom
    ├── link_zoom_product.py    # Vincula produto ao Zoom
    ├── report_price_history.py # Relatório de histórico
    ├── create_shopee_session.py # Cria sessão Shopee (login)
    └── run-config.example.json # Exemplo de config
```

## Dependências
- **Python 3.12+** (stdlib apenas para os scripts originais)
- **fastapi** — servidor HTTP
- **uvicorn** — servidor ASGI
- **playwright** — browser headless com stealth
- **Chromium** — `playwright install chromium`
- **Dependências de sistema**: `libnspr4`, `libnss3` (e outras libs listadas pelo `playwright install-deps`)

## Como usar

### 1. Instalar dependências
```bash
pip install fastapi uvicorn playwright
playwright install chromium
# Se der erro de libs do sistema:
sudo apt install -y libnspr4 libnss3
```

### 2. Iniciar o servidor de scraping
```bash
cd .agents/skills/price-alert-skill/scripts
python3 scrape_server.py --port 3000
```

### 3. Usar os fetchers
```bash
python3 fetch_amazon_br.py "ssd 2tb" --api-base http://localhost:3000
python3 fetch_mercadolivre_br.py "placa de video" --api-base http://localhost:3000
python3 fetch_shopee_br.py "memoria ram" --api-base http://localhost:3000
```

### 4. Criar uma watchlist
```bash
python3 onboard_watchlist.py ../references/watchlist-onboarding.example.json --bootstrap --db-path ../data/price_history.sqlite3
```

## Decisões tomadas nesta sessão

### Substituição do Steel Browser
- **Problema**: A skill original dependia do Steel Browser (`localhost:3000`), um serviço de scraping headless pago/externo.
- **Solução**: Criado `scrape_server.py`, um servidor local com Playwright + Chromium que replica a mesma API do Steel (`POST /v1/scrape`, `POST /v1/sessions`, `GET /v1/sessions/{id}/context`).
- **Stealth**: O servidor usa técnicas anti-detecção: user-agent aleatório, viewport randomizado, injeção de JS para ocultar `navigator.webdriver`, headers realistas.

### Shopee — login não automatizado
- A Shopee tem proteção anti-bot agressiva (interstitial, CAPTCHA).
- Foi implementado endpoint `POST /v1/sessions/{id}/login` que abre Chromium com GUI para login manual.
- **Conclusão**: Login manual é inviável porque cookies expiram em ~12h. Shopee fica pendente para solução futura.
- Sem login, a Shopee frequentemente retorna interstitial em vez de resultados.

### Status dos marketplaces (31/03/2026)
| Marketplace | Status | Observação |
|---|---|---|
| Amazon BR | Funcionando | Stealth efetivo, sem bloqueios |
| Mercado Livre | Funcionando | Stealth efetivo, sem bloqueios |
| Shopee BR | Parcial | Interstitial anti-bot, login inviável |

### Estrutura do repositório
- Inicialmente criado na pasta raiz `agentSkills/`
- Reorganizado para `.agents/skills/price-alert-skill/` seguindo convenção
- Branch renomeada de `master` para `main`

## Endpoints do scrape_server.py
| Endpoint | Método | Descrição |
|---|---|---|
| `/v1/scrape` | POST | Scraping de URL. Body: `{"url": "...", "delay": N}` |
| `/v1/sessions` | POST | Cria sessão para login |
| `/v1/sessions/{id}/context` | GET | Retorna cookies da sessão |
| `/v1/sessions/{id}/login` | POST | Abre Chromium com GUI para login Shopee |
| `/v1/sessions/{id}/save` | POST | Salva cookies explícitos |
| `/v1/sessions/{id}/check` | GET | Verifica status de login |

## Possíveis melhorias futuras
- **Shopee**: Usar `undetected-chromedriver` (requer Chrome instalado) ou API oficial
- **Zoom**: O enriquecimento via Zoom pode precisar de ajustes nos extraction rules
- **Agendamento**: Implementar cron/scheduler para atualizações recorrentes
- **Notificações**: Integração real com WhatsApp (atualmente gera apenas texto formatado)
- **Testes**: Adicionar testes unitários para parsers e fetchers

## Comandos úteis
```bash
# Testar fetcher específico
python3 fetch_amazon_br.py "ssd 2tb" --api-base http://localhost:3000 --max-results 5

# Ver histórico de preços
python3 report_price_history.py --db-path ../data/price_history.sqlite3

# Gerar alertas
python3 generate_alert_payloads.py --query "ssd 2tb" --db-path ../data/price_history.sqlite3
```
