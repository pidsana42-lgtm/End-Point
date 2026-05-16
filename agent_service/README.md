# PartsPro AI Agent Service

> **Microservice** สำหรับ AI Agent ที่ใช้ Typhoon LLM จัดการระบบสั่งซื้ออะไหล่รถยนต์  
> แยกออกจาก Backend หลักเพื่อให้ระบบภายนอกสามารถเชื่อมต่อได้ผ่าน HTTP

---

## Architecture Overview

```
ระบบภายนอก / Frontend / LINE Bot
         │
         │  POST /chat
         ▼
┌─────────────────────────────┐
│   agent_service  (Port 8001)│
│   Typhoon LLM + Tool Calling│
└────────────┬────────────────┘
             │ import database.py
             ▼
    bills_v2.db (SQLite)
```

---

## Quick Start

### 1. ติดตั้ง Dependencies

```bash
cd agent_service
pip install -r requirements.txt
```

### 2. ตั้งค่า Environment Variables

```bash
export TYPHOON_API_KEY="sk-xxxxxxxxxxxxxxxxxxxx"
export BACKEND_PATH="../ai_bill_scanner"   # path ไปยังโฟลเดอร์ที่มี database.py
```

### 3. รัน Service

```bash
python agent_service.py
# หรือ
uvicorn agent_service:app --host 0.0.0.0 --port 8001 --reload
```

---

## API Reference

### `GET /health`

ตรวจสอบสถานะ service

**Response:**
```json
{
  "status": "ok",
  "service": "agent_service",
  "port": 8001
}
```

---

### `POST /chat`

ส่งข้อความสนทนาให้ AI และรับคำตอบกลับ

**URL:** `http://localhost:8001/chat`  
**Method:** `POST`  
**Content-Type:** `application/json`

#### Request Body

```json
{
  "messages": [
    { "role": "user", "content": "มีน้ำมันเครื่อง Castrol 5W-30 ไหมครับ" }
  ],
  "user_id": "Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `messages` | `array` | ✅ | ประวัติการสนทนา (**ต้องส่งทุกครั้ง** เพื่อให้ AI จำบริบทได้) |
| `messages[].role` | `string` | ✅ | `"user"` หรือ `"assistant"` |
| `messages[].content` | `string` | ✅ | ข้อความ |
| `user_id` | `string` | ❌ | ID ผู้ใช้ (สำหรับ logging) |

#### Response Body

```json
{
  "reply": "มีครับ! [CAST-5W30] Castrol GTX 5W-30 ราคา 320 บาท เหลือ 48 ชิ้น",
  "user_id": "Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "tool_used": "search_products"
}
```

| Field | Type | Description |
|---|---|---|
| `reply` | `string` | ข้อความตอบกลับจาก AI |
| `user_id` | `string` | ส่งกลับมาเหมือนเดิม |
| `tool_used` | `string` | ชื่อ tool ที่ AI เรียกใช้ (ว่างถ้าไม่ได้ใช้ tool) |

---

## ตัวอย่างการใช้งาน

### Python (httpx)

```python
import httpx

AGENT_URL = "http://localhost:8001"

async def chat(messages: list[dict], user_id: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            f"{AGENT_URL}/chat",
            json={"messages": messages, "user_id": user_id}
        )
        return res.json()["reply"]

# ตัวอย่างการใช้งาน
messages = [
    {"role": "user", "content": "ดูรายการสินค้าในคลังหน่อยครับ"}
]
reply = await chat(messages, user_id="user_001")
print(reply)
```

### JavaScript (fetch)

```javascript
async function chat(messages, userId) {
  const res = await fetch("http://localhost:8001/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, user_id: userId })
  });
  const data = await res.json();
  return data.reply;
}

// ตัวอย่าง
const messages = [
  { role: "user", content: "สร้างออเดอร์ให้ลูกค้า สมชาย น้ำมันเครื่อง 2 ขวด" }
];
const reply = await chat(messages, "user_001");
console.log(reply);
```

### cURL

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "มีอะไหล่อะไรบ้าง"}],
    "user_id": "test_user"
  }'
```

---

## Tool Capabilities

AI Agent มีความสามารถต่อไปนี้ (เรียกใช้ tool อัตโนมัติจากภาษาธรรมชาติ):

| Tool | คำสั่งตัวอย่าง |
|---|---|
| `search_products` | "มีผ้าเบรค Brembo ไหม" |
| `get_inventory_ai` | "ดูสินค้าในคลังทั้งหมด" |
| `create_preorder_ai` | "สั่งน้ำมันเครื่อง 5 ขวดให้สมชาย" |
| `get_preorders_ai` | "ดูรายการออเดอร์ทั้งหมด" |
| `get_order_details_ai` | "ดูรายละเอียดออเดอร์ ID 3" |
| `update_preorder_status_ai` | "อนุมัติออเดอร์ ID 3" |
| `add_product_ai` | "เพิ่มสินค้าใหม่ ไส้กรองอากาศ ราคา 250" |
| `update_inventory_ai` | "อัปเดตสต็อก SKU-001 เป็น 50 ชิ้น" |
| `delete_product_ai` | "ลบสินค้า รหัส AI-1234" |
| `analyze_data_ai` | "สรุปยอดขายทั้งหมด" |

---

## Multi-turn Conversation (การสนทนาต่อเนื่อง)

Agent ไม่มี built-in session — **ระบบที่เรียกใช้ต้องเก็บ history เอง** และส่งมาทุกครั้ง

```python
# ✅ ถูกต้อง: ส่ง history ทุกครั้ง
history = []

def send(text: str):
    history.append({"role": "user", "content": text})
    reply = chat(history, user_id="u001")
    history.append({"role": "assistant", "content": reply})
    return reply

send("มีน้ำมันเครื่อง Castrol ไหม")
send("ราคาเท่าไหร่")          # AI จะยังจำบริบทว่าถาม Castrol
send("สั่ง 3 ขวดได้เลย")     # AI จะสร้าง preorder อัตโนมัติ
```

> **หมายเหตุ:** แนะนำให้จำกัด history ไม่เกิน **10 messages** เพื่อประสิทธิภาพ

---

## Error Handling

| กรณี | Reply ที่ได้รับ |
|---|---|
| Agent service ไม่ได้รัน | `"ขออภัยครับ ไม่สามารถเชื่อมต่อ Agent Service ได้..."` |
| Response timeout (>60s) | `"ขออภัยครับ Agent ใช้เวลาตอบสนองนานเกินไป..."` |
| Internal error | `"ขออภัยครับ ระบบ Agent ขัดข้อง (Error: ...)"` |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TYPHOON_API_KEY` | *(required)* | API Key จาก https://opentyphoon.ai |
| `BACKEND_PATH` | `../ai_bill_scanner` | Path ไปยังโฟลเดอร์ที่มี `database.py` |

---

## Swagger UI

เมื่อ service รันแล้ว เข้าดู API docs ได้ที่:

```
http://localhost:8001/docs
```
