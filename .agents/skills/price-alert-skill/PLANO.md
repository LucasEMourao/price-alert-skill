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
**Status:** Definido

**Formato fornecido pelo usuário:**
```
🎸 OFERTA DO DIA 👇 

🎚️ Guitarra Fender Squier Debut Stratocaster Hss Lr Green Orientação Da Mão Destro Verde-claro Pau-rosa

🎯 Hoje: R$ 1604.26

🛍️ Comprar aqui:
https://meli.la/2KwVAYY

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

**Padrão identificado:**
1. **Linha 1:** Emoji temático + título da oferta + emoji seta
2. **Linha 2 (vazia)**
3. **Linha 3:** Emoji + nome completo do produto
4. **Linha 4 (vazia)**
5. **Linha 5:** Emoji + preço atual (formato `R$ XXXX.XX`, ponto como separador decimal)
6. **Linha 6 (vazia)**
7. **Linha 7:** Emoji + texto "Comprar aqui:"
8. **Linha 8:** Link curto/direto do produto
9. **Linha 9 (vazia)**
10. **Linha 10:** Emoji + aviso sobre variação de valores/estoque

**Adaptação para nosso caso (ofertas de tech gamer):**
- Emoji temático pode variar: 🎮 🖥️ ⌨️ 🎧 🖱️ 💻 conforme o tipo de produto
- **Preço:** mostrar preço atual + comparação com preço anterior quando houver desconto (gera gatilho de urgência/escassez)
- Link: usar link direto do marketplace (Amazon/MercadoLivre/Shopee)
- Aviso final: manter a frase de escassez

**Exemplo gerado (sem desconto — primeiro registro):**
```
⌨️ OFERTA DO DIA 👇 

🖱️ HyperX Pulsefire Haste 2 Wireless - Mouse Gamer Sem Fio, 8000 DPI, 61g

🎯 Hoje: R$ 249.90

🛍️ Comprar aqui:
https://www.amazon.com.br/dp/B0BX4F5R2P

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

**Exemplo gerado (com desconto — gera gatilho):**
```
🖱️ OFERTA DO DIA 👇 

⌨️ HyperX Pulsefire Haste 2 Wireless - Mouse Gamer Sem Fio, 8000 DPI, 61g

🎯 Hoje: R$ 189.90
📉 Era: R$ 299.90
🔥 Desconto: 37% OFF

🛍️ Comprar aqui:
https://www.amazon.com.br/dp/B0BX4F5R2P

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

**Regras para exibir comparação:**
- Só exibir `📉 Era:` e `🔥 Desconto:` quando o desconto for >= 5% em relação ao último preço registrado
- `Era:` usa o último preço anterior não-nulo do banco
- `Desconto:` é calculado como `((preço_anterior - preço_atual) / preço_anterior) * 100`, arredondado para inteiro
- Se não houver preço anterior ou desconto < 5%, exibir apenas o preço atual (formato simples)

---

### Etapa 2: Configurar categoria de produtos específica
**Status:** Definido (implementação pendente)

**Categoria definida pelo usuário:** Tecnologia gamer para computadores/notebooks

**Subcategorias a monitorar:**

| Subcategoria | Exemplos de busca |
|---|---|
| Mouse gamer | "mouse gamer", "mouse sem fio gamer", "mouse RGB" |
| Teclado mecânico | "teclado mecanico gamer", "teclado gamer RGB" |
| Headset gamer | "headset gamer", "fone gamer", "headset sem fio" |
| Monitor gamer | "monitor gamer", "monitor 144hz", "monitor 240hz" |
| SSD/NVMe | "ssd 2tb", "ssd nvme", "ssd gamer" |
| Memória RAM | "memoria ram ddr5", "memoria ram gamer" |
| Placa de vídeo | "placa de video", "rtx 4060", "rtx 4070" |
| Notebook gamer | "notebook gamer", "notebook rtx" |
| Gabinete gamer | "gabinete gamer", "gabinete rgb" |
| Fonte gamer | "fonte gamer", "fonte 850w" |
| Cooler | "cooler gamer", "water cooler" |
| Cadeira gamer | "cadeira gamer" |
| Mousepad | "mousepad gamer", "mousepad grande" |
| Webcam gamer | "webcam gamer", "webcam streaming" |
| Controle gamer | "controle gamer", "controle sem fio" |

**O que será feito:**
1. Criar watchlist(s) no SQLite via `onboard_watchlist.py` para cada subcategoria
2. Configurar `update_interval_minutes: 5`
3. Marketplaces: `amazon_br` e `mercadolivre_br` (Shopee fica de fora por enquanto)
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
**Status:** Definido (implementação pendente)

**O que será feito:**
1. Adaptar `format_whatsapp_alerts.py` para o formato do usuário
2. Gerar uma mensagem por produto com preço abaixo da média
3. Incluir imagem do produto (se disponível no scraping)
4. Formato compatível com WhatsApp

**Template da mensagem (sem desconto):**
```
{emoji_categoria} OFERTA DO DIA 👇 

{emoji_produto} {NOME_COMPLETO_DO_PRODUTO}

🎯 Hoje: R$ {PRECO_ATUAL}

🛍️ Comprar aqui:
{LINK_DIRETO}

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

**Template da mensagem (com desconto >= 5%):**
```
{emoji_categoria} OFERTA DO DIA 👇 

{emoji_produto} {NOME_COMPLETO_DO_PRODUTO}

🎯 Hoje: R$ {PRECO_ATUAL}
📉 Era: R$ {PRECO_ANTERIOR}
🔥 Desconto: {PERCENTUAL}% OFF

🛍️ Comprar aqui:
{LINK_DIRETO}

🎵 Valores podem variar. Se entrar em estoque baixo, some rápido.
```

**Emojis por categoria:**
- Mouse: 🖱️
- Teclado: ⌨️
- Headset/Fone: 🎧
- Monitor: 🖥️
- SSD/HD: 💾
- Memória RAM: 🧩
- Placa de vídeo: 🎮
- Notebook: 💻
- Gabinete: 🏠
- Fonte: ⚡
- Cooler: ❄️
- Cadeira: 🪑
- Mousepad: 🎯
- Webcam: 📷
- Controle: 🎮
- Outros: 🎮
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

| Etapa | Descrição | Dependências | Status |
|---|---|---|---|
| 1 | Definir formato mensagem | Nenhuma | **Concluído** |
| 2 | Configurar categoria/watchlist | Etapa 1 | **Concluído** |
| 3 | Implementar agendamento | Etapa 2 | **Concluído** |
| 4 | Lógica preço abaixo da média | Etapa 3 | **Concluído** |
| 5 | Formatar mensagens WhatsApp | Etapa 1 | **Concluído** |
| 6 | Integrar pipeline completo | Etapas 3-5 | **Concluído** |
| 7 | Integração WhatsApp (opcional) | Etapa 6 | A fazer |

---

## Próximos passos imediatos

1. ~~Etapa 2: Criar watchlists para subcategorias gamer~~ ✅
2. ~~Etapa 3: Implementar scheduler.py para rodar a cada 5 minutos~~ ✅
3. ~~Etapa 4: Implementar lógica de detecção de preço abaixo da média~~ ✅
4. ~~Etapa 5: Adaptar format_deal_messages.py para o template definido~~ ✅
5. **Etapa 7:** Integração com WhatsApp (automática ou manual)
