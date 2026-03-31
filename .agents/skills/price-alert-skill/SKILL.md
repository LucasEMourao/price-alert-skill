---
name: price-alert-monitor
description: Monitore precos de produtos na Amazon Brasil, Mercado Livre e Shopee Brasil usando um Steel browser em execucao, armazene historico em SQLite, enriqueça a base com referencias do Zoom e gere alertas deduplicados prontos para WhatsApp. Use esta skill quando o usuario quiser criar watchlists por categoria ou links, atualizar monitoramentos recorrentes a cada N minutos ou receber alertas de ofertas em marketplaces brasileiros.
---

# Price Alert Monitor

Use esta skill para o fluxo completo de monitoramento de precos em marketplaces brasileiros.

Esta skill foi empacotada como uma unidade unica:
- busca resultados na Amazon BR, Mercado Livre e Shopee BR
- grava historico de precos em SQLite
- suporta onboarding por `categories[]` e links opcionais
- roda atualizacoes recorrentes a cada `N` minutos
- enriquece produtos com baselines historicos do Zoom
- gera payloads deduplicados para mensagens de WhatsApp

## Comportamento Padrrao

- Sempre tente executar o fluxo, nao responda apenas com comandos para o usuario rodar.
- Quando o usuario pedir para criar monitoramentos, monte o JSON internamente e rode o onboarding.
- Quando o usuario pedir atualizacoes, rode o pipeline em segundo plano na propria resposta.
- Quando o usuario nao especificar watchlist, atualize todas as watchlists ativas.
- Responda em PT-BR por padrao.

## Quando Usar

- O usuario quer monitorar uma ou mais categorias.
- O usuario enviou links de produtos e quer acompanhar os precos.
- O usuario quer atualizacoes agendadas e apenas alertas relevantes.
- O usuario quer mensagens prontas para WhatsApp.

## UX Do Usuario

No onboarding, nao peca JSON manualmente a menos que o usuario queira isso explicitamente.

Em vez disso:
1. Leia o pedido em linguagem natural.
2. Infira uma ou mais watchlists.
3. Monte o payload JSON internamente.
4. Rode o onboarding.
5. Resuma em linguagem simples o que foi criado.

Boas entradas naturais:
- `monitor SSD 2TB e placa de video a cada 30 minutos na Amazon e Mercado Livre`
- `acompanhe cafeteira espresso e air fryer, me avise de promocoes, atualize a cada 60 minutos`
- `quero seguir estes links e tambem monitorar a categoria notebook gamer`

Se o usuario der varios objetivos independentes, divida em varias watchlists.

Exemplos:
- `monitor SSD 2TB a cada 30 minutos e GPU a cada 2 horas`
  Crie 2 watchlists porque a cadencia muda.
- `monitor SSD 2TB, memoria DDR5 e placa de video a cada 30 minutos`
  Crie 1 watchlist com `categories[]` porque a cadencia e os marketplaces sao compartilhados.
- `monitor estes 2 links da Amazon e este produto do Mercado Livre`
  Crie 1 ou mais watchlists dependendo se a cadencia parece unica ou separada.

## Fluxo

1. Crie uma ou mais watchlists com `scripts/onboard_watchlist.py`.
2. Use `--bootstrap` para popular imediatamente os primeiros snapshots.
3. Para pedidos de atualizacao do usuario, rode `scripts/refresh_watchlist_messages.py` e devolva apenas a mensagem final.
4. Use `scripts/update_watchlist.py` apenas quando precisar dos detalhes estruturados da execucao.
5. Use `scripts/generate_alert_payloads.py` apenas para debug ou extensao da logica.
6. Use Zoom apenas como baseline externo, nunca como fonte primaria do preco atual.
7. Por padrao, quando um produto ainda tem menos de 2 snapshots locais com preco, consulte o Zoom automaticamente para categorias elegiveis.

## Scripts Principais

- `scripts/onboard_watchlist.py`
  Cria watchlists a partir de categorias, queries e links.
- `scripts/refresh_watchlist_messages.py`
  Roda a atualizacao e devolve apenas as mensagens finais.
- `scripts/update_watchlist.py`
  Roda atualizacoes estruturadas para watchlists pendentes.
- `scripts/generate_alert_payloads.py`
  Gera facts deterministicas para mensagens.

Os comandos abaixo existem como referencia interna. Prefira executa-los voce mesmo em vez de pedir para o usuario rodar:

```bash
python scripts/onboard_watchlist.py ... --bootstrap
python scripts/refresh_watchlist_messages.py --force
python scripts/update_watchlist.py
python scripts/generate_alert_payloads.py --query "ssd 2tb"
```

## Formato De Entrada

O onboarding exige:
- `update_interval_minutes`
- um de: `categories`, `category`, `queries` ou `query`

Voce pode criar varias watchlists de uma vez usando um array raiz `watchlists[]`.

Comportamento preferido:
- Se o usuario der um conjunto de categorias com uma unica cadencia, crie uma watchlist.
- Se o usuario der grupos diferentes com cadencias ou marketplaces diferentes, crie varias watchlists.
- Se o usuario nao informar marketplaces, use `amazon_br`, `mercadolivre_br` e `shopee_br`.
- Se o usuario nao informar nome, gere um nome curto e claro.
- Se o usuario passar links e categoria, mantenha ambos.
- Se o usuario pedir atualizacao sem especificar watchlist, atualize todas as watchlists ativas.

Campos opcionais:
- `name`
- `marketplaces`
- `target_price`
- `notes`
- `links[]`
- per-link `title`
- per-link `category`
- per-link `zoom_url`
- per-link `session_id` para Shopee

Se o usuario passar `categories[]`, essas frases viram as queries principais. Se o usuario passar links, a skill tambem deriva refinamentos por item.

## Mapeamento De Linguagem Natural

Traduza o pedido natural para JSON antes de chamar os scripts.

Regras de mapeamento:
- frases de produto/categoria viram `categories[]`
- `every 30 minutes`, `a cada 30 minutos` -> `update_interval_minutes: 30`
- `Amazon` -> `amazon_br`
- `Mercado Livre` -> `mercadolivre_br`
- `Shopee` -> `shopee_br`
- metas de preco como `below R$ 1800`, `ate 1800` -> `target_price: 1800`
- URLs explicitas de produto entram em `links[]`

Entrada natural:

```text
Monitor SSD 2TB e placa de video na Amazon e Mercado Livre a cada 30 minutos.
```

Payload montado pelo agente:

```json
{
  "name": "Hardware deals",
  "categories": ["ssd 2tb", "placa de video"],
  "marketplaces": ["amazon_br", "mercadolivre_br"],
  "update_interval_minutes": 30
}
```

Entrada natural:

```text
Quero acompanhar SSD 2TB a cada 30 minutos e notebook gamer a cada 120 minutos.
```

Payload montado pelo agente:

```json
{
  "watchlists": [
    {
      "name": "SSD 2TB",
      "categories": ["ssd 2tb"],
      "marketplaces": ["amazon_br", "mercadolivre_br", "shopee_br"],
      "update_interval_minutes": 30
    },
    {
      "name": "Notebook Gamer",
      "categories": ["notebook gamer"],
      "marketplaces": ["amazon_br", "mercadolivre_br", "shopee_br"],
      "update_interval_minutes": 120
    }
  ]
}
```

Entrada natural:

```text
Monitora esses links e também a categoria memória DDR5. Atualiza a cada 45 minutos.
```

Payload montado pelo agente:

```json
{
  "name": "Memoria e seeds",
  "categories": ["memoria ddr5"],
  "marketplaces": ["amazon_br", "mercadolivre_br", "shopee_br"],
  "update_interval_minutes": 45,
  "links": [
    {
      "url": "https://..."
    }
  ]
}
```

Quando fizer sentido, mostre rapidamente a interpretacao antes ou depois do onboarding:
- `Criei 2 watchlists: SSD 2TB a cada 30 minutos e Notebook Gamer a cada 120 minutos.`

Para atualizacoes:
- Rode o pipeline completo em segundo plano na propria resposta.
- Devolva apenas os blocos finais de mensagem de WhatsApp.
- Se o usuario nao especificar watchlist, atualize todas as watchlists ativas.
- Se nao houver descontos relevantes, devolva exatamente: `Sem descontos encontrados no momento.`
- Nao mostre produtos com movimentos de preco fracos ou irrelevantes.
- Se uma watchlist seeded estiver estreita demais, atualize tanto as queries dos seeds quanto as queries amplas da watchlist.
- Em watchlists novas, enriqueça produtos com Zoom automaticamente quando a categoria parecer elegivel.
- Trate `preco atual < mediana do Zoom` como sinal valido de desconto mesmo sem historico local maduro.

## Referencias Importantes

- Use [references/storage-layout.md](references/storage-layout.md) para o schema SQLite.
- Use [references/output-schema.md](references/output-schema.md) para os campos JSON dos fetchers.
- Use [references/extraction-rules-amazon.md](references/extraction-rules-amazon.md) se o parsing da Amazon quebrar.
- Use [references/extraction-rules-mercadolivre.md](references/extraction-rules-mercadolivre.md) se o parsing do Mercado Livre quebrar.
- Use [references/extraction-rules-shopee.md](references/extraction-rules-shopee.md) se o parsing da Shopee quebrar.
- Use [references/extraction-rules-zoom.md](references/extraction-rules-zoom.md) se o enriquecimento via Zoom precisar de ajuste.
- Use [references/watchlist-onboarding.example.json](references/watchlist-onboarding.example.json) como exemplo minimo de onboarding.
- Use [references/watchlist-hardware.example.json](references/watchlist-hardware.example.json) e [references/watchlist-placas-de-video-rtx.example.json](references/watchlist-placas-de-video-rtx.example.json) apenas como exemplos adicionais.

## Guardrails

- O servidor de scraping (`scripts/scrape_server.py`) deve estar rodando em `http://localhost:3000`.
  - Iniciar com: `python3 scripts/scrape_server.py --port 3000`
  - Dependencias: `pip install fastapi uvicorn playwright && playwright install chromium`
  - Usa Playwright com stealth para evitar detecção de bots.
- Amazon BR e Mercado Livre funcionam sem autenticação.
- Shopee BR pode retornar interstitial (proteção anti-bot). Login automático não é suportado atualmente.
- Mantenha snapshots diretos dos marketplaces como fonte principal da verdade para alertas.
- Trate o Zoom apenas como contexto externo.
- Nao emita alertas duplicados; use o fingerprint de `alert_events`.
- Trate quedas abaixo de `1%` como nao acionaveis por padrao.
- O enriquecimento automatico via Zoom funciona melhor em categorias de eletronicos e eletrodomesticos.
