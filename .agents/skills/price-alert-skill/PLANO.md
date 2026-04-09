# PLANO — Monitor de Ofertas com Alertas WhatsApp

## Objetivo Final
Buscar ofertas em marketplaces brasileiros (Amazon BR, Mercado Livre), extrair descontos exibidos pelo próprio marketplace, e enviar mensagens com imagens automaticamente para grupos de WhatsApp.

---

## Status Atual: ✅ FUNCIONANDO

O pipeline de busca e formatação está implementado e testado. O script principal é `scan_deals.py`.

---

## Abordagem Escolhida

**Decisão do usuário:** Repassar apenas o desconto que o marketplace exibe. Se o site mostra "de R$ 2.000 por R$ 1.500 com 25% OFF", essa é a informação oficial. Não é necessário validar se é "promoção real".

**Vantagens:**
- Sem banco de dados (SQLite)
- Sem agendamento complexo
- Scraping sob demanda
- Zero manutenção

---

## Como Usar

```bash
# 1. Iniciar servidor de scraping
cd .agents/skills/price-alert-skill/scripts
python3 scrape_server.py --port 3000

# 2. Buscar ofertas de uma categoria
python3 scan_deals.py "mouse gamer" --min-discount 10

# 3. Buscar TODAS as categorias gamer
python3 scan_deals.py --all --min-discount 10
```

---

## O que já foi feito

| Item | Descrição |
|---|---|
| Servidor de scraping | `scrape_server.py` com Playwright + stealth (substitui Steel Browser) |
| Fetcher Amazon | Extrai preço atual + preço anterior riscado (`list_price`) + **gera link afiliado automaticamente** |
| Fetcher Mercado Livre | Parser reescrito para nova estrutura HTML — extrai preço atual + preço anterior riscado |
| Script principal | `scan_deals.py` — busca ofertas e gera mensagens WhatsApp |
| Formato das mensagens | Template com preço antigo riscado (`~~...~~`) acima do preço atual |
| Categorias gamer | 12 queries de busca configuradas em `scan_deals.py` |
| Código consolidado | `utils.py` com funções compartilhadas |
| Deduplicação cross-session | `sent_deals.json` — evita repetir ofertas entre execuções (limpeza automática a cada 7 dias) |
| **Links afiliados Amazon** | `config.py` + `build_affiliate_url()` em `fetch_amazon_br.py` — URLs sanitizadas para `/dp/{ASIN}?tag=brunoentende-20` |
| Dependências | `requirements.txt` com fastapi, uvicorn, playwright |
| Testes automatizados | 75 testes unitários (utils, Amazon parser + afiliados, ML parser) |
| Zoom/Shopee/SQLite | Removidos (pipeline legado descartado) |

---

## Formato da Mensagem WhatsApp

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

**Regras:**
- Preço antigo riscado aparece acima do preço atual (mais intuitivo)
- `Era:` e `Desconto:` só aparecem quando desconto >= `--min-discount` (padrão: 10%)
- Se não houver preço anterior exibido, mostra apenas preço atual
- Link do produto gera preview com imagem automaticamente no WhatsApp

---

## Próximos Passos

### Passo 1: Implementar links afiliados Mercado Livre
**Status:** Pendente — aguardando teste de formato de URL

Para implementar, é necessário:
1. Testar se `produto.mercadolivre.com.br/MLB_ID?matt_word=...&matt_tool=...` funciona (pode perder parâmetros no redirect)
2. Se não funcionar, experimentar formato alternativo (`www.mercadolivre.com.br/p/MLB_ID?matt_word=...`)
3. Implementar `build_affiliate_url()` em `fetch_mercadolivre_br.py`
4. Configurar `ML_MATT_WORD` e `ML_MATT_TOOL` em `config.py`

### Passo 2: Implementar envio automático para WhatsApp
**Objetivo:** Enviar imagens + mensagens automaticamente via WhatsApp Web, com a mensagem como legenda da imagem para melhor experiência do usuário.

**Estratégia escolhida: Imagem com legenda (melhor experiência)**
1. Baixar imagem do produto antes de enviar
2. Enviar a imagem como mídia no WhatsApp Web (via Selenium/Playwright) **com a mensagem formatada como legenda**
3. Repetir para cada produto

**Benefícios desta abordagem:**
- Experiência mais natural no WhatsApp (como quando enviamos fotos com legenda manualmente)
- Apenas uma notificação em vez de duas
- Imagem e texto permanecem visualmente agrupados
- Link na legenda ainda gera preview automaticamente no WhatsApp

**Arquivos a criar:**
- `scripts/send_to_whatsapp.py` — script de envio via WhatsApp Web

**Dependências a adicionar:**
- `selenium` ou `pywhatkit` para automação do WhatsApp Web
- `requests` ou `httpx` para download das imagens

---

## Categorias Monitoradas

Configuradas em `scan_deals.py` (variável `GAMER_QUERIES`):
- mouse gamer
- teclado mecanico gamer
- headset gamer
- monitor gamer
- ssd 2tb
- memoria ram ddr5
- placa de video rtx
- notebook gamer
- gabinete gamer
- fonte gamer
- cooler gamer
- mousepad gamer

---

## Histórico de Decisões

1. **Steel Browser → Playwright local** — Substituímos dependência externa por servidor local
2. **Shopee descartada** — Proteção anti-bot inviabiliza uso sem login manual constante
3. **SQLite → Sem banco** — Decisão do usuário: repassar apenas dados exibidos pelo marketplace
4. **Agendamento → Sob demanda** — Não é necessário agendar; usuário executa quando quiser
5. **Parser Mercado Livre reescrito** — HTML mudou; agora usa `aria-label` para preços
6. **Preço antigo riscado acima** — Formato mais intuitivo visualmente
7. **Imagem via link** — Link do produto no final gera preview automático no WhatsApp
8. **Código Shopee removido** — ~225 linhas de endpoints de sessão/login removidos do scrape_server.py
9. **Deduplicação cross-session** — `sent_deals.json` com limpeza automática (7 dias)
10. **Testes automatizados** — 75 testes unitários para parsers, utils e geração de links afiliados
11. **Links afiliados Amazon BR** — URLs sanitizadas para `/dp/{ASIN}?tag=brunoentende-20` via `build_affiliate_url()`

---

## Histórico de Commits

| Commit | Descrição |
|---|---|
| `37203b1` | Refactor: remove SQLite/Zoom pipeline, consolidate code, fix ML parser |
| `c8384da` | Update CONTEXT.md and PLANO.md with simplified approach |
| `4c823e4` | Add scan_deals.py - simplified approach without SQLite |
