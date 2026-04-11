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
| Fetcher Mercado Livre | Parser reescrito para nova estrutura HTML — extrai preço atual + preço anterior riscado + **gera link afiliado** |
| Script principal | `scan_deals.py` — busca ofertas e gera mensagens WhatsApp |
| Formato das mensagens | Template atualizado: % OFF primeiro, depois "Antes:" e "Hoje:", links meli.la |
| Categorias gamer | 12 queries de busca configuradas em `scan_deals.py` |
| Código consolidado | `utils.py` com funções compartilhadas |
| Deduplicação cross-session | `sent_deals.json` — evita repetir ofertas entre execuções (limpeza automática a cada 7 dias) |
| **Links afiliados Amazon** | `config.py` + `build_affiliate_url()` em `fetch_amazon_br.py` — URLs sanitizadas para `/dp/{ASIN}?tag=brunoentende-20` |
| **Links afiliados ML** | `config.py` + `build_affiliate_url()` em `fetch_mercadolivre_br.py` — **FUNCIONANDO** via agent-browser (`fetch_ml_browser.py`) — extrai links reais do HTML renderizado |
| **Links meli.la ML** | `generate_melila_links.py` — gera links meli.la via painel de afiliados do ML (com login automático, cache e fallback) |
| Dependências | `requirements.txt` com fastapi, uvicorn, playwright + agent-browser (npm global) |
| Testes automatizados | 96 testes unitários (utils, Amazon parser + afiliados, ML parser + afiliados, browser fetcher) |
| Zoom/Shopee/SQLite | Removidos (pipeline legado descartado) |

---

## Formato da Mensagem WhatsApp

```
{emoji} OFERTA DO DIA 👇

{emoji} {NOME_PRODUTO}

🔥 {PERCENTUAL}% OFF
💰 Antes: R$ {PRECO_ANTERIOR}
🎯 Hoje: R$ {PRECO_ATUAL}

🛍️ Comprar aqui:
{LINK}

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

**Regras:**
- `% OFF` aparece primeiro (mais impactante)
- `Antes:` sem strikethrough, linha separada
- `Hoje:` preço atual na última linha de preço
- Se não houver preço anterior exibido, mostra apenas preço atual
- Link do produto gera preview com imagem automaticamente no WhatsApp
- Links ML usam formato `meli.la` (gerados via painel de afiliados) quando possível

---

## Próximos Passos

### Passo 1: ~~Implementar links afiliados~~ ✅ Parcial
- **Amazon BR**: Links afiliados gerados automaticamente via `?tag=brunoentende-20` — **funcionando e testado**
- **Mercado Livre**: Parâmetros de afiliado (`?matt_word=...&matt_tool=...`) prontos, mas **URLs construídas do ID são frágeis**. Formato `MLB-{number}-_JM` funciona para alguns IDs mas falha para outros. ML carrega produtos via JavaScript e não inclui links reais no HTML estático, impossibilitando extração dos links verdadeiros sem renderização JS.
- **Correção ML**: URL base alterada de `produto.mercadolivre.com.br/MLB_ID` (404) para `produto.mercadolivre.com.br/MLB-{number}-_JM` (hífen obrigatório). **Ainda não é 100% confiável.**

### Passo 1.5: ~~Implementar agent browser para ML~~ ✅ Concluído
**Implementação concluída em 10/04/2026.**

**O que foi feito:**
1. Instalado `agent-browser` globalmente via npm (`npm install -g agent-browser`)
2. Baixado Chrome for Testing (`agent-browser install`)
3. Criado `scripts/fetch_ml_browser.py` — novo fetcher que usa agent-browser CLI para:
   - Navegar nos resultados de busca do ML com JavaScript renderizado
   - Extrair os **links reais** dos cards de produto (ex: `https://www.mercadolivre.com.br/mouse-gamer-redragon-cobra-rgb-preto-preto/p/MLB8752191`)
   - Extrair preço atual (`aria-label="Agora:"`) e preço anterior (`aria-label="Antes:"`)
   - Anexar parâmetros de afiliado (`?matt_word=...&matt_tool=...`) automaticamente
4. Atualizado `scan_deals.py` para usar `fetch_ml_browser.py` em vez do servidor Playwright para ML
5. Adicionados 17 testes unitários em `tests/test_ml_browser.py`
6. Total: 96 testes passando (79 + 17)

**Como funciona:**
- O agent-browser abre Chrome em modo headless com user-agent personalizado
- Navega para `lista.mercadolivre.com.br/{query}`
- Aguarda o `networkidle` (JavaScript renderiza os produtos)
- Executa JS no browser para extrair título, URL real, preços e imagem
- Fecha o browser e retorna os dados estruturados

**Arquivos criados/modificados:**
- `scripts/fetch_ml_browser.py` — novo fetcher (agent-browser)
- `scripts/tests/test_ml_browser.py` — 17 testes unitários
- `scripts/scan_deals.py` — atualizado para usar browser fetcher para ML

### Passo 2: ~~Implementar envio automático para WhatsApp~~ ⏳ PAUSADO
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

### Passo 3: Gerar links meli.la via painel de afiliados ✅ FUNCIONANDO (via proxy)
**Implementação concluída e testada em 11/04/2026.**

**O que foi feito:**
1. Criado `scripts/generate_melila_links.py` — módulo de geração de links meli.la via agent-browser
2. Atualizado `scripts/config.py` — adicionado `ML_AFFILIATE_EMAIL`, `ML_AFFILIATE_PASSWORD` e `ML_PROXY`
3. Atualizado `scripts/scan_deals.py` — integrado geração de meli.la com flag `--no-melila` para fallback
4. Atualizado `scripts/utils.py` — formato da mensagem alterado (% OFF primeiro, "Antes:" sem strikethrough)
5. Atualizado `scripts/tests/test_utils.py` — testes compatíveis com novo formato
6. 96 testes passando

**Descobertas sobre o Gerador de Links:**
- URL: `mercadolivre.com.br/afiliados/linkbuilder`
- Campo de texto: `textbox "Insira 1 ou mais URLs separados por 1 linha"` — aceita múltiplas URLs
- Botão: `button "Gerar"` (desabilitado até URL ser preenchida)
- Resultado: `textbox "Copie o link e comece a compartilhá-lo"` (singular) ou `textbox "Copie seus links e comece a compartilhá-los"` (plural)
- Formato de URL aceito: `https://www.mercadolivre.com.br/{slug}/p/MLB{id}`
- Links gerados: formato `https://meli.la/XXXXX`
- Suporte a "Link curto" (meli.la) e "Link completo" (URL completa)

**Como funciona:**
- O `scan_deals.py` chama `generate_links()` após extrair deals
- `generate_melila_links.py` navega até o Gerador de Links via agent-browser
- Preenche o campo com as URLs dos produtos (uma por linha para múltiplas)
- Clica "Gerar" e extrai os meli.la gerados
- Cache em `data/melila_cache.json` evita regerar links já criados
- Fallback: se geração falhar, usa URL longa com `matt_word`/`matt_tool`

**Proxy obrigatório:**
- IP do servidor é bloqueado pelo ML CloudFront (403)
- Usar variável de ambiente `ML_PROXY` ou flag `--proxy` no agent-browser
- Proxy gratuito para testes: `http://200.174.198.32:8888` (proxy brasileiro)

**Arquivos criados/modificados:**
- `scripts/generate_melila_links.py` — módulo de geração meli.la (refatorado com seletores corretos)
- `scripts/config.py` — credenciais + proxy configurados
- `scripts/scan_deals.py` — integração com meli.la + flag `--no-melila`
- `scripts/utils.py` — formato da mensagem atualizado
- `scripts/tests/test_utils.py` — testes atualizados

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
10. **Testes automatizados** — 96 testes unitários para parsers, utils e geração de links afiliados
11. **Links afiliados Amazon BR** — URLs sanitizadas para `/dp/{ASIN}?tag=brunoentende-20` via `build_affiliate_url()` — **funcionando**
12. **Links afiliados Mercado Livre** — Parâmetros prontos, URLs extraídas do HTML renderizado via agent-browser — **funcionando**
13. **Correção URL ML** — agent-browser substitui construção frágil de URLs por extração de links reais do JavaScript renderizado
14. **Imagem removida do texto da mensagem** — `image_url` mantido no dict para uso futuro por `send_to_whatsapp.py`, mas não aparece mais no texto
15. **Agent-browser para ML** — `fetch_ml_browser.py` usa CLI Rust para renderizar páginas ML e extrair URLs reais com slug — **96 testes passando**
16. **Links meli.la via painel de afiliados** — `generate_melila_links.py` gera links meli.la automaticamente via agent-browser logado no painel de afiliados — **FUNCIONANDO via proxy**
17. **Formato da mensagem atualizado** — % OFF primeiro, "Antes:" sem strikethrough, alinhado ao modelo do cliente
18. **matt_word e matt_tool verificados** — Confirmados como corretos via redirecionamento de link meli.la
19. **Proxy obrigatório para ML** — IP do servidor bloqueado pelo ML CloudFront; proxy residencial brasileiro necessário
20. **Geração em lote de meli.la** — Gerador de Links aceita múltiplas URLs separadas por newline

---

## Histórico de Commits

| Commit | Descrição |
|---|---|
| `37203b1` | Refactor: remove SQLite/Zoom pipeline, consolidate code, fix ML parser |
| `c8384da` | Update CONTEXT.md and PLANO.md with simplified approach |
| `4c823e4` | Add scan_deals.py - simplified approach without SQLite |
| `HEAD` | Implement agent-browser for ML - real product URLs extracted from rendered HTML |
