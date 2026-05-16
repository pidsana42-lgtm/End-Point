# PartsPro AI Agent Service

> **Production-ready Microservice** สำหรับ AI Agent ที่ใช้ Typhoon LLM  
> แยกออกจาก Backend หลักอย่างสมบูรณ์ — คุยกัน **ผ่าน HTTP API เท่านั้น**  
> ทุก tool call ป้องกันด้วย `X-Agent-Key` header

---

## Architecture

```
[ LINE OA / Frontend / External System ]
              │  POST /chat
              ▼
┌──────────────────────────┐    X-Agent-Key     ┌──────────────────────────┐
│   agent_service          │ ─────────────────►  │   backend (main.py)      │
│   Port: 8001             │ ◄─────────────────  │   Port: 8000             │
│                          │    JSON response    │                          │
│  - Typhoon LLM           │                     │  - FastAPI + SQLite      │
│  - Tool Calling          │                     │  - bills_v2.db           │
│  - Text-to-SQL proxy     │                     │  - LINE Webhook          │
│                          │                     │  - Bill Scanner OCR      │
│  ❌ ไม่มี DB             │                     │  ✅ owns DB ทั้งหมด      │
│  ❌ ไม่มี shared code    │                     │                          │
└──────────────────────────┘                     └──────────────────────────┘
```

---

## ทดสอบบน Local 🖥️

> **ใช่! ทดสอบบน local ได้ทันที** โดยรันทั้ง 2 service พร้อมกันบนเครื่องเดียว

### ขั้นตอน

**1. เปิด Terminal 1 — รัน Backend (port 8000)**

```bash
cd ai_bill_scanner

# ตั้งค่า env
export GEMINI_API_KEY="AIza..."
export LINE_CHANNEL_ACCESS_TOKEN="..."
export LINE_CHANNEL_SECRET="..."
export AGENT_API_KEY="local-test-key"   # ← กำหนดเองได้

# รัน
python main.py
```

**2. เปิด Terminal 2 — รัน Agent (port 8001)**

```bash
cd agent_service

# copy .env
cp .env.example .env
# แก้ไข .env ให้ครบ:
#   TYPHOON_API_KEY=sk-xxx
#   BACKEND_API_URL=http://localhost:8000   ← ชี้ไปที่ local backend
#   AGENT_API_KEY=local-test-key            ← ต้องตรงกับ backend

python agent_service.py
```

**3. ทดสอบ Health Check**

```bash
# ตรวจสอบ agent + backend reachable
curl http://localhost:8001/health
```

ผลลัพธ์ที่ถูกต้อง:
```json
{
  "status": "ok",
  "service": "agent_service",
  "port": 8001,
  "backend_url": "http://localhost:8000",
  "backend_reachable": true
}
```

**4. ทดสอบ Chat**

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "มีสินค้าอะไรในคลังบ้าง"}],
    "user_id": "test_user"
  }'
```

---

## การติดตั้ง

```bash
cd agent_service
pip install -r requirements.txt
cp .env.example .env
# แก้ไขค่าใน .env
python agent_service.py
```

---

## Environment Variables

### `agent_service/.env`

| Variable | Required | Default | Description |
|---|---|---|---|
| `TYPHOON_API_KEY` | ✅ | — | API Key จาก https://opentyphoon.ai |
| `BACKEND_API_URL` | ✅ | `http://localhost:8000` | URL ของ Backend service |
| `AGENT_API_KEY` | ✅ | — | Shared secret กับ backend (ต้องตรงกัน) |
| `AGENT_PORT` | ❌ | `8001` | Port ที่ agent รัน |

### `ai_bill_scanner/.env` (Backend)

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google Gemini สำหรับ OCR สแกนบิล |
| `LINE_CHANNEL_ACCESS_TOKEN` | ✅ | LINE OA token |
| `LINE_CHANNEL_SECRET` | ✅ | LINE OA secret |
| `AGENT_API_KEY` | ✅ | Shared secret (ต้องตรงกับ agent) |

> **หมายเหตุ:** `AGENT_API_KEY` ต้องเป็นค่าเดียวกันทั้งสอง `.env`  
> ถ้า backend ไม่ตั้งค่า `AGENT_API_KEY` = development mode (ไม่มี auth)

---

## API Reference

### `GET /health`

ตรวจสอบสถานะ service + ว่า backend reachable ไหม

```json
{
  "status": "ok",
  "service": "agent_service",
  "port": 8001,
  "backend_url": "http://localhost:8000",
  "backend_reachable": true
}
```

---

### `POST /chat`

**URL:** `http://localhost:8001/chat`

#### Request

```json
{
  "messages": [
    { "role": "user", "content": "มีน้ำมันเครื่อง Castrol ไหมครับ" }
  ],
  "user_id": "Uxxxxxxxxxxxxxx"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `messages` | `array` | ✅ | ประวัติการสนทนา (ต้องส่งทุกรอบสำหรับ multi-turn) |
| `messages[].role` | `string` | ✅ | `"user"` หรือ `"assistant"` |
| `messages[].content` | `string` | ✅ | ข้อความ |
| `user_id` | `string` | ❌ | ID ผู้ใช้ (สำหรับ logging) |

#### Response

```json
{
  "reply": "มีครับ! [CAST-5W30] Castrol GTX 5W-30 ราคา 320 บาท เหลือ 48 ชิ้น",
  "user_id": "Uxxxxxxxxxxxxxx",
  "tool_used": "search_products"
}
```

---

## Tool Capabilities

| Tool | คำสั่งตัวอย่าง | Backend Endpoint |
|---|---|---|
| `search_products` | "มีผ้าเบรค Brembo ไหม" | `GET /api/agent/parts/search` |
| `get_inventory_ai` | "ดูสินค้าในคลังทั้งหมด" | `GET /api/parts` |
| `create_preorder_ai` | "สั่งน้ำมัน 5 ขวดให้สมชาย" | `POST /api/preorders` |
| `get_preorders_ai` | "ดูรายการออเดอร์ทั้งหมด" | `GET /api/agent/preorders` |
| `get_order_details_ai` | "ดูออเดอร์ ID 3" | `GET /api/agent/preorders/{id}` |
| `update_preorder_status_ai` | "อนุมัติออเดอร์ ID 3" | `PATCH /api/agent/preorders/{id}/status` |
| `add_product_ai` | "เพิ่มสินค้า ไส้กรอง ราคา 250" | `POST /api/parts/add` |
| `update_inventory_ai` | "อัปเดตสต็อก SKU-001 เป็น 50" | `PATCH /api/agent/parts/{code}/stock` |
| `delete_product_ai` | "ลบสินค้า รหัส AI-1234" | `DELETE /api/agent/parts/{code}` |
| `analyze_data_ai` | "สรุปยอดขายทั้งหมด" | `GET /api/agent/analysis` |
| `run_query_ai` | "ยอดขายเดือนนี้เท่าไหร่" | `POST /api/agent/query` (Text-to-SQL) |

---

## Multi-turn Conversation

Agent ไม่มี built-in session — **ระบบที่เรียกต้องเก็บ history เองและส่งมาทุกครั้ง**

```python
import httpx

history = []

def send(text: str) -> str:
    history.append({"role": "user", "content": text})
    res = httpx.post("http://localhost:8001/chat",
                     json={"messages": history, "user_id": "u001"})
    reply = res.json()["reply"]
    history.append({"role": "assistant", "content": reply})
    # แนะนำ: จำกัด history ไม่เกิน 10 messages
    if len(history) > 10:
        history[:] = history[-10:]
    return reply

send("มีน้ำมัน Castrol ไหม")
send("ราคาเท่าไหร่")       # AI ยังจำบริบทว่าถามเรื่อง Castrol
send("สั่ง 3 ขวดเลย")      # AI สร้าง preorder อัตโนมัติ
```

---

## Production Deployment

```bash
# Server A — Backend
export GEMINI_API_KEY="AIza..."
export LINE_CHANNEL_ACCESS_TOKEN="..."
export LINE_CHANNEL_SECRET="..."
export AGENT_API_KEY="your-strong-secret"   # ← เปลี่ยน!
python main.py                              # port 8000

# Server B — Agent (คนละ server ได้เลย)
export TYPHOON_API_KEY="sk-..."
export BACKEND_API_URL="http://<IP_SERVER_A>:8000"
export AGENT_API_KEY="your-strong-secret"   # ← ต้องตรงกัน
export AGENT_PORT=8001
python agent_service.py
```

---

## Backend Agent Endpoints (ต้องมี `X-Agent-Key`)

Endpoints เหล่านี้ถูกเพิ่มไว้ใน `main.py` สำหรับให้ agent เรียกโดยเฉพาะ:

```
GET    /api/agent/preorders
GET    /api/agent/preorders/{id}
PATCH  /api/agent/preorders/{id}/status
GET    /api/agent/parts/search?q=...
PATCH  /api/agent/parts/{code}/stock
DELETE /api/agent/parts/{code}
GET    /api/agent/analysis
POST   /api/agent/query          ← Text-to-SQL (SELECT only)
```

ระบบภายนอกที่ต้องการเรียก endpoints เหล่านี้โดยตรงต้องส่ง:
```
X-Agent-Key: your-agent-api-key
```

---

## Swagger UI

```
http://localhost:8001/docs    ← Agent Service API Docs
http://localhost:8000/docs    ← Backend API Docs
```
