# PLANO — Monitor de Preços com Alertas WhatsApp

## Objetivo Final
Monitorar preços de produtos em marketplaces brasileiros (Amazon BR, Mercado Livre, Shopee BR), atualizar a cada 5 minutos, e gerar mensagens formatadas para grupos de WhatsApp sempre que um preço estiver abaixo da média/histórico.

---

## O que já fizemos

### 1. Skill base (pronta)
- Scripts de scraping para Amazon BR, Mercado Livre e Shopee BR
- Banco SQLite com schema para produtos, snapshots de preço, alertas e watchlists
- Servidor `scrape_server.py` com Playwright + stealth (substitui Steel Browser)
- Scripts de onboarding, atualização e geração de alertas
- Formatação de mensagens WhatsApp (`format_whatsapp_alerts.py`)

### 2. O que funciona hoje
- Amazon BR: scraping sem bloqueios
- Mercado Livre: scraping sem bloqueios
- Shopee BR: parcial (interstitial anti-bot, login inviável — cookies 12h)

### 3. O que NÃO está pronto
- Agendamento automático a cada 5 minutos (não implementado)
- Detecção de "preço abaixo da média" em tempo real
- Mensagens no formato específico do usuário (**pendente: usuário precisa descrever o formato da foto**)
- Envio real para WhatsApp (atualmente gera apenas texto)

---

## Etapas do Plano

### Etapa 1: Definir o formato da mensagem WhatsApp
**Status:** Pendente (aguardando descrição do usuário)

O usuário mencionou uma foto com o padrão desejado, mas o modelo não consegue ler imagens.
**Ação necessária:** Usuário deve descrever o formato textualmente ou colar um exemplo de mensagem.

Elementos típicos de uma mensagem de alerta de oferta:
- Emoji de alerta/oferta (🔥, 🏷️, 💰)
- Nome do produto
- Preço atual vs preço anterior/média
- Percentual de desconto
- Link direto para o produto
- Marketplace de origem
- Timestamp da captura

---

### Etapa 2: Configurar categoria de produtos específica
**Status:** A fazer

**O que será feito:**
1. Definir com o usuário qual categoria monitorar (ex: "SSD 2TB", "placa de vídeo RTX", "notebook gamer")
2. Criar watchlist no SQLite via `onboard_watchlist.py`
3. Configurar `update_interval_minutes: 5`
4. Rodar `--bootstrap` para popular dados iniciais

**Arquivo de configuração:** `.agents/skills/price-alert-skill/references/watchlist-onboarding.example.json`

---

### Etapa 3: Implementar agendamento de 5 em 5 minutos
**Status:** A fazer

**Opções avaliadas:**

| Abordagem | Prós | Contras |
|---|---|---|
| **cron (Linux)** | Simples, nativo, confiável | Precisa de acesso ao sistema |
| **schedule (Python)** | Código puro Python, fácil de manter | Processo precisa ficar rodando |
| **APScheduler** | Robusto, suporte a jobs persistentes | Dependência extra |
| **systemd timer** | Nativo Linux, logs integrados | Mais complexo de configurar |

**Recomendação:** Usar `schedule` (Python puro) ou `cron`. Para simplicidade, um script `scheduler.py` que roda em loop:

```python
import schedule
import time

schedule.every(5).minutes.do(run_update_cycle)

while True:
    schedule.run_pending()
    time.sleep(1)
```

**Alternativa com cron:**
```cron
*/5 * * * * cd /path/to/scripts && python3 update_watchlist.py --force
```

---

### Etapa 4: Lógica de detecção de preço abaixo da média
**Status:** A fazer

**O que será feito:**
1. Consultar histórico de preços do produto no SQLite (`price_snapshots`)
2. Calcular média móvel dos últimos N snapshots (ex: últimos 20)
3. Definir threshold de desconto (ex: 5% abaixo da média)
4. Gerar alerta apenas quando `preço_atual < média * (1 - threshold)`

**SQL conceitual:**
```sql
SELECT AVG(price) as media
FROM price_snapshots
WHERE product_id = ?
  AND price IS NOT NULL
  AND captured_at > datetime('now', '-7 days');
```

**Regras de alerta:**
- Preço atual deve ser não-nulo
- Deve haver pelo menos 3 snapshots anteriores
- Desconto mínimo de 5% para gerar alerta
- Evitar alertas duplicados (usar `fingerprint` na tabela `alert_events`)

---

### Etapa 5: Formatar mensagens para WhatsApp
**Status:** A fazer (depende da Etapa 1)

**O que será feito:**
1. Adaptar `format_whatsapp_alerts.py` para o formato desejado pelo usuário
2. Incluir: produto, preço, desconto %, link, marketplace
3. Formato compatível com WhatsApp (negrito `*texto*`, itálico `_texto_`, código ```texto```)
4. Limitar tamanho da mensagem (WhatsApp tem limite de 4096 caracteres)

**Estrutura sugerida (ajustar conforme padrão do usuário):**
```
🔥 *OFERTA NO RADAR!*

📦 *Produto:* Samsung 990 PRO 2TB NVMe
💰 *Preço atual:* R$ 1.539,90
📉 *Preço médio:* R$ 1.899,00
🏷️ *Desconto:* 19% off
🛒 *Marketplace:* Amazon BR
🔗 *Link:* https://...

⏰ _Atualizado em 31/03/2026 às 21:00_
```

---

### Etapa 6: Pipeline completo integrado
**Status:** A fazer

**Fluxo:**
```
┌─────────────────┐
│  Scheduler       │  (a cada 5 min)
│  (cron/schedule) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Update Watchlist│  Scraping Amazon/MercadoLivre/Shopee
│  (fetchers)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SQLite          │  Salva snapshots de preço
│  (price_history) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Alert Engine    │  Compara com média histórica
│  (nova lógica)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Message Builder │  Formata mensagem WhatsApp
│  (format_alerts) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  WhatsApp        │  Copia/cola ou API de envio
│  (manual ou API) │
└─────────────────┘
```

---

### Etapa 7: Integração com WhatsApp (opcional)
**Status:** A fazer (se necessário)

**Opções:**
| Método | Complexidade | Custo |
|---|---|---|
| Copiar mensagem para clipboard | Baixa | Grátis |
| WhatsApp Web automation (Selenium) | Média | Grátis |
| WhatsApp Business API | Alta | Pago por mensagem |
| `pywhatkit` | Baixa | Grátis (abre WhatsApp Web) |
| Baileys (Node.js) | Média | Grátis (não oficial) |

**Recomendação inicial:** Gerar o texto e o usuário cola manualmente no grupo. Depois evoluir para automação.

---

## Cronograma sugerido

| Etapa | Descrição | Dependências | Estimativa |
|---|---|---|---|
| 1 | Definir formato mensagem | Nenhuma | Aguardando usuário |
| 2 | Configurar categoria/watchlist | Etapa 1 | 30 min |
| 3 | Implementar agendamento | Etapa 2 | 1 hora |
| 4 | Lógica preço abaixo da média | Etapa 3 | 1 hora |
| 5 | Formatar mensagens WhatsApp | Etapa 1 | 30 min |
| 6 | Integrar pipeline completo | Etapas 3-5 | 1 hora |
| 7 | Integração WhatsApp (opcional) | Etapa 6 | 2+ horas |

---

## Próximos passos imediatos

1. **Usuário descreve o formato da mensagem WhatsApp** (ou cola exemplo textual)
2. **Usuário define a categoria de produtos** a ser monitorada
3. Começamos pela Etapa 2 (criar watchlist) e Etapa 3 (agendamento)
