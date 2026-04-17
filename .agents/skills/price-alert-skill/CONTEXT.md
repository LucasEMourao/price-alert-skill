# Context — price-alert-skill

## Resumo

`price-alert-skill` é um pipeline de scraping sob demanda para marketplaces brasileiros. O fluxo atual busca ofertas na Amazon BR e no Mercado Livre, filtra produtos com desconto mínimo, gera links de afiliado, formata mensagens para WhatsApp e pode enviar automaticamente essas mensagens pelo WhatsApp Web.

O projeto não depende de banco de dados relacional nem de servidor de scraping dedicado para o fluxo principal.

## Fluxo que está valendo hoje

1. `scripts/scan_deals.py` é o ponto de entrada principal.
2. Amazon BR é coletada por `scripts/fetch_amazon_br.py` usando Playwright sync API.
3. Mercado Livre é coletado por `scripts/fetch_ml_browser.py` usando Playwright sync API e leitura do DOM renderizado.
4. Ofertas novas são deduplicadas com base em `data/sent_deals.json`.
5. Ofertas do Mercado Livre tentam virar `meli.la` via `scripts/generate_melila_links.py`.
6. As mensagens são formatadas por `scripts/utils.py`.
7. Quando `--send-whatsapp` é usado, o envio acontece por `scripts/send_to_whatsapp.py`.

## Estrutura relevante

```text
.agents/skills/price-alert-skill/
├── SKILL.md
├── CONTEXT.md
├── PLANO.md
├── .env.example
├── requirements.txt
├── data/
│   ├── melila_cache.json
│   ├── ml_session.json
│   ├── sent_deals.json
│   ├── messages/
│   └── whatsapp_session/
├── references/
└── scripts/
    ├── config.py
    ├── scan_deals.py
    ├── fetch_amazon_br.py
    ├── fetch_ml_browser.py
    ├── fetch_mercadolivre_br.py
    ├── generate_melila_links.py
    ├── send_to_whatsapp.py
    ├── scrape_server.py
    ├── utils.py
    └── tests/
```

## Componentes ativos

- `scripts/scan_deals.py`
  Coordena a busca, deduplicação, geração de mensagens e envio opcional para WhatsApp.

- `scripts/fetch_amazon_br.py`
  Busca resultados na Amazon BR e converte URLs para o formato afiliado com `AMAZON_AFFILIATE_TAG`.

- `scripts/fetch_ml_browser.py`
  Busca resultados no Mercado Livre usando Playwright direto. Este é o caminho principal para ML hoje.

- `scripts/generate_melila_links.py`
  Usa sessão persistida do painel de afiliados do Mercado Livre para gerar links `meli.la`.

- `scripts/send_to_whatsapp.py`
  Usa uma sessão persistida do WhatsApp Web para enviar imagem + legenda para um grupo.

- `scripts/config.py`
  Carrega o `.env` e centraliza configurações como `AMAZON_AFFILIATE_TAG` e `WHATSAPP_GROUP`.

## Componentes legados

- `scripts/scrape_server.py`
  Mantido no repositório, mas não faz parte do fluxo principal. Não é necessário iniciar servidor para usar a skill hoje.

- `scripts/fetch_mercadolivre_br.py`
  Parser legado do Mercado Livre baseado em HTML estático. O caminho principal atual é `fetch_ml_browser.py`.

## Variáveis de ambiente

- `AMAZON_AFFILIATE_TAG`
  Obrigatória para gerar links afiliados da Amazon com a tag correta.

- `WHATSAPP_GROUP`
  Grupo padrão usado por `scan_deals.py` e `send_to_whatsapp.py`. O parâmetro de linha de comando continua disponível como sobrescrita manual.

- `ML_PROXY`
  Proxy opcional para cenários em que o painel de afiliados do Mercado Livre bloquear o IP.

- `ML_AFFILIATE_EMAIL` e `ML_AFFILIATE_PASSWORD`
  Mantidas no `.env.example` para referência, embora o login atual seja manual pelo navegador.

## Estado persistido em disco

- `data/sent_deals.json`
  Evita reenviar ofertas já processadas recentemente. A limpeza automática remove entradas antigas.

- `data/melila_cache.json`
  Cache de URLs do Mercado Livre já convertidas para `meli.la`.

- `data/ml_session.json`
  Sessão persistida do painel de afiliados do Mercado Livre.

- `data/whatsapp_session/`
  Perfil persistido do WhatsApp Web.

- `data/messages/deals_*.json`
  Saída gerada por execuções do `scan_deals.py`.

## Comandos de referência

```bash
# Instalação
pip install -r requirements.txt
playwright install chromium

# Login manual no Mercado Livre afiliados
python3 scripts/generate_melila_links.py --login

# Buscar ofertas
python3 scripts/scan_deals.py "mouse gamer" --min-discount 10
python3 scripts/scan_deals.py --all --min-discount 10

# Enviar para o grupo padrão do .env
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp

# Sobrescrever o grupo do .env
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp --whatsapp-group "Grupo de Teste"

# Login inicial do WhatsApp
python3 scripts/scan_deals.py --all --min-discount 10 --send-whatsapp --headed

# Uso direto do sender
python3 scripts/send_to_whatsapp.py --deals data/messages/deals_YYYYMMDD_HHMMSS.json

# Testes
python3 -m pytest tests/ -v
```

## Decisões importantes do projeto

- O pipeline usa scraping sob demanda e não histórico em banco.
- O desconto confiado é o que o marketplace exibe.
- O envio de WhatsApp depende de sessão persistida e de seletor compatível com a UI atual do WhatsApp Web.
- O grupo padrão de envio agora pode vir do `.env`, evitando hardcode no comando do fluxo end-to-end.

## Observações de manutenção

- Mudanças no HTML da Amazon BR, do Mercado Livre ou do WhatsApp Web podem quebrar seletores e exigir ajustes.
- A documentação foi limpa para refletir apenas o fluxo vivo; se algum arquivo legado voltar a ser usado, isso deve ser documentado explicitamente antes.
