# PLANO — Monitor de Ofertas com Alertas WhatsApp

## Objetivo Final
Buscar ofertas em marketplaces brasileiros (Amazon BR, Mercado Livre), extrair descontos exibidos pelo próprio marketplace, e gerar mensagens formatadas para grupos de WhatsApp.

---

## Status Atual: ✅ FUNCIONANDO

O pipeline básico está implementado e testado. O script principal é `scan_deals.py`.

---

## Abordagem Escolhida

**Decisão do usuário:** Repassar apenas o desconto que o marketplace exibe. Se o site mostra "de R$ 2.000 por R$ 1.500 com 25% OFF", essa é a informação oficial. Não é necessário validar se é "promoção real" — a responsabilidade é do marketplace.

**Vantagens:**
- Sem banco de dados (SQLite)
- Sem agendamento complexo
- Scraping sob demanda
- Zero manutenção

**Limitação aceita:** Descontos exibidos podem ser inflados artificialmente pelo vendedor, mas não é nossa responsabilidade validar.

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

### ✅ Concluído
| Item | Descrição |
|---|---|
| Servidor de scraping | `scrape_server.py` com Playwright + stealth (substitui Steel Browser) |
| Fetcher Amazon | Extrai preço atual + preço anterior riscado (`list_price`) |
| Fetcher Mercado Livre | Extrai preço atual (preço anterior pendente) |
| Script principal | `scan_deals.py` — busca ofertas e gera mensagens WhatsApp |
| Formato das mensagens | Template definido com emojis por categoria |
| Categorias gamer | 12 queries de busca configuradas em `scan_deals.py` |

### ⏳ Pendente
| Item | Descrição |
|---|---|
| Mercado Livre list_price | Parser não extrai preço anterior riscado ainda |
| Integração WhatsApp | Mensagens são salvas em arquivo, não enviadas automaticamente |
| Shopee BR | Descartada (proteção anti-bot inviabiliza) |

---

## Formato da Mensagem WhatsApp

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

**Regras:**
- `📉 Era:` e `🔥 Desconto:` só aparecem quando desconto >= `--min-discount` (padrão: 10%)
- Se não houver preço anterior exibido, mostra apenas preço atual

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
5. **Parser Amazon atualizado** — Agora extrai `list_price` (preço anterior riscado)

---

## Possíveis Melhorias Futuras

| Prioridade | Melhoria | Descrição |
|---|---|---|
| Alta | Mercado Livre list_price | Ajustar parser para extrair preço anterior |
| Média | Filtro por preço mínimo | Ignorar produtos muito baratos (acessórios genéricos) |
| Média | Deduplicação | Evitar repetir ofertas já enviadas |
| Baixa | Integração WhatsApp | Enviar via pywhatkit ou WhatsApp Business API |
| Baixa | Mais marketplaces | Adicionar Kabum, Pichau, Terabyte |
