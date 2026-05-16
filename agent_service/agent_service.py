"""
agent_service.py — PartsPro AI Agent Microservice (Port 8001)
=============================================================
Production-ready: ไม่มี direct DB access
ทุก tool call ไปผ่าน Backend API (BACKEND_API_URL) พร้อม X-Agent-Key
"""

import os
import re
import json
import uvicorn
import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from openai import OpenAI

# โหลด .env อัตโนมัติ (ถ้ามี python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
AGENT_API_KEY   = os.environ.get("AGENT_API_KEY", "")
TYPHOON_API_KEY = os.environ.get("TYPHOON_API_KEY", "")

_HEADERS = {"X-Agent-Key": AGENT_API_KEY, "Content-Type": "application/json"}

# ─────────────────────────────────────────────────────────────────────────────
# App + LLM Client
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PartsPro AI Agent Service",
    version="2.0.0",
    description="Production-ready AI Agent — communicates with backend via REST API only."
)

typhoon_client = OpenAI(
    api_key=TYPHOON_API_KEY,
    base_url="https://api.opentyphoon.ai/v1"
)

# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str       # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    user_id: str = "unknown"

class ChatResponse(BaseModel):
    reply: str
    user_id: str
    tool_used: str = ""

# ─────────────────────────────────────────────────────────────────────────────
# HTTP helper (sync — ใช้ภายใน tool functions)
# ─────────────────────────────────────────────────────────────────────────────
def _get(path: str, **params) -> dict | list:
    url = f"{BACKEND_API_URL}{path}"
    r = httpx.get(url, headers=_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def _post(path: str, body: dict) -> dict:
    url = f"{BACKEND_API_URL}{path}"
    r = httpx.post(url, headers=_HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def _patch(path: str, body: dict) -> dict:
    url = f"{BACKEND_API_URL}{path}"
    r = httpx.patch(url, headers=_HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def _delete(path: str) -> dict:
    url = f"{BACKEND_API_URL}{path}"
    r = httpx.delete(url, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

# ─────────────────────────────────────────────────────────────────────────────
# Tool Functions — ทุกตัวใช้ HTTP ไปหา backend เท่านั้น
# ─────────────────────────────────────────────────────────────────────────────

def search_products(query: str) -> str:
    try:
        parts = _get("/api/agent/parts/search", q=query, limit=5)
        if not parts:
            return "ไม่พบสินค้าที่ตรงกับการค้นหาครับ"
        res = "รายการสินค้าที่พบ:\n"
        for p in parts:
            res += f"- [{p['part_code']}] {p['part_name']} | ราคา: {p['price']} บาท | คงเหลือ: {p['stock']} ชิ้น\n"
        return res
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการค้นหา: {str(e)}"


def create_preorder_ai(customer_name: str, items_json: str,
                       customer_phone: str = "", company_name: str = "") -> str:
    from datetime import datetime
    try:
        items = json.loads(items_json)
        body = {
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "company_name": company_name or "สั่งซื้อผ่าน AI",
            "order_date": datetime.now().strftime("%Y-%m-%d"),
            "total_amount": 0,
            "items": items
        }
        result = _post("/api/preorders", body)
        order_id = result.get("id", 0)
        return f"สร้างรายการพรีออเดอร์สำเร็จแล้วครับ! เลขที่รายการ: PRE-{order_id:04d}"
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการสร้างรายการ: {str(e)}"


def add_product_ai(part_name: str, price: float) -> str:
    import random
    try:
        part_code = f"AI-{random.randint(1000, 9999)}"
        # ใช้ multipart form — เรียกผ่าน httpx โดยตรง
        r = httpx.post(
            f"{BACKEND_API_URL}/api/parts/add",
            headers={"X-Agent-Key": AGENT_API_KEY},
            data={"part_code": part_code, "part_name": part_name, "price": str(price)},
            files={"files": ("placeholder.txt", b"", "text/plain")},
            timeout=30
        )
        return f"เพิ่มสินค้า '{part_name}' รหัส '{part_code}' ราคา {price} บาท เรียบร้อยแล้วครับ!"
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการเพิ่มสินค้า: {str(e)}"


def get_preorders_ai() -> str:
    try:
        orders = _get("/api/agent/preorders", limit=10)
        if not orders:
            return "ยังไม่มีรายการพรีออเดอร์ในขณะนี้ครับ"
        res = "รายการพรีออเดอร์ล่าสุด:\n"
        for o in orders:
            res += f"- [ID: {o['id']}] {o['customer_name']} | ยอด: ฿{o['total_amount']:,.2f} | สถานะ: {o['status']}\n"
        return res
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการดึงข้อมูล: {str(e)}"


def update_preorder_status_ai(order_id: int, status: str) -> str:
    try:
        _patch(f"/api/agent/preorders/{order_id}/status", {"status": status})
        return f"อัปเดตสถานะรายการ ID {order_id} เป็น '{status}' เรียบร้อยแล้วครับ!"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"ไม่พบรายการ ID {order_id} ในระบบครับ"
        return f"เกิดข้อผิดพลาด: {str(e)}"


def get_order_details_ai(order_id: int) -> str:
    try:
        order = _get(f"/api/agent/preorders/{order_id}")
        items = json.loads(order.get('items', '[]'))
        res = f"รายละเอียดรายการ ID {order_id} ({order['customer_name']}):\n"
        res += f"วันที่: {order['order_date']} | สถานะ: {order['status']}\nยอดรวม: ฿{order['total_amount']:,.2f}\nรายการสินค้า:\n"
        for i in items:
            res += f"- {i.get('part_name', 'N/A')} x {i.get('quantity', 0)} | ฿{i.get('amount', 0):,.2f}\n"
        return res
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"ไม่พบรายการ ID {order_id} ครับ"
        return f"เกิดข้อผิดพลาด: {str(e)}"


def get_inventory_ai() -> str:
    try:
        parts = _get("/api/parts")
        if not parts:
            return "ไม่มีสินค้าในคลังครับ"
        res = "รายการสินค้าในคลังทั้งหมด:\n"
        for p in parts:
            res += f"- [{p['part_code']}] {p['part_name']} | ราคา: ฿{p['price']:,.2f} | คงเหลือ: {p.get('stock', 0)} ชิ้น\n"
        return res
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการดึงข้อมูล: {str(e)}"


def update_inventory_ai(part_code: str, quantity: int) -> str:
    try:
        _patch(f"/api/agent/parts/{part_code}/stock", {"quantity": quantity})
        return f"อัปเดตสต็อกสินค้า [{part_code}] เป็นจำนวน {quantity} ชิ้น เรียบร้อยแล้วครับ!"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"ไม่พบรหัสสินค้า [{part_code}] ในระบบครับ"
        return f"เกิดข้อผิดพลาด: {str(e)}"


def delete_product_ai(part_code: str) -> str:
    try:
        _delete(f"/api/agent/parts/{part_code}")
        return f"ลบสินค้า [รหัส: {part_code}] ออกจากระบบเรียบร้อยแล้วครับ!"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"ไม่พบรหัสสินค้า [{part_code}] ในระบบครับ"
        return f"เกิดข้อผิดพลาด: {str(e)}"


def analyze_data_ai() -> str:
    try:
        data = _get("/api/agent/analysis")
        res = "📊 รายงานวิเคราะห์ข้อมูลร้านค้า:\n"
        res += f"💰 ยอดขายที่อนุมัติแล้ว: ฿{data.get('total_sales_approved', 0):,.2f}\n"
        bill_stats = data.get('bill_scanned_stats', {})
        res += f"📄 บิลที่สแกนแล้ว: {bill_stats.get('count', 0)} ใบ (รวม ฿{bill_stats.get('total') or 0:,.2f})\n"
        res += "\n🏆 ลูกค้าประจำ (Top 5):\n"
        for c in data.get('top_customers', []):
            res += f"- {c['customer_name']}: {c['count']} รายการ\n"
        res += "\n⚠️ สินค้าใกล้หมด (Stock < 5):\n"
        low = data.get('low_stock_items', [])
        if low:
            for i in low:
                res += f"- {i['part_name']}: เหลือ {i['stock']} ชิ้น\n"
        else:
            res += "- ไม่มีสินค้าใกล้หมด\n"
        return res
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการวิเคราะห์ข้อมูล: {str(e)}"


def run_query_ai(question: str) -> str:
    """Text-to-SQL: สร้าง SQL จากภาษาธรรมชาติ แล้วส่งไปให้ backend execute"""
    SCHEMA = """
    Tables in bills_v2.db:
    1. bills(id, invoice_no, supplier, date, po_ref, total, items_json, created_at)
    2. preorders(id, customer_name, customer_phone, company_name, order_date, total_amount, items, status, created_at)
    3. spare_parts(id, part_code, part_name, price, stock, created_at)
    4. part_images(id, part_id, image_path, is_primary)
    """
    try:
        # Step 1: ให้ Typhoon สร้าง SQL
        sql_response = typhoon_client.chat.completions.create(
            model="typhoon-v2.5-30b-a3b-instruct",
            messages=[
                {"role": "system", "content": (
                    f"You are a SQLite expert. Schema:\n{SCHEMA}\n"
                    "Generate a single SELECT SQL query. Output ONLY raw SQL — no markdown, no semicolons."
                )},
                {"role": "user", "content": question}
            ],
            temperature=0.1,
            max_tokens=256
        )
        sql = sql_response.choices[0].message.content.strip()
        if "```" in sql:
            m = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", sql)
            sql = m.group(1).strip() if m else sql.replace("```", "").strip()

        print(f">>> [Text-to-SQL] Q: {question} | SQL: {sql}")

        # Step 2: ส่ง SQL ไปให้ backend รัน
        result = _post("/api/agent/query", {"sql": sql})
        rows = result.get("rows", [])
        if not rows:
            return "ไม่พบข้อมูลตรงกับเงื่อนไขที่ถามครับ"

        headers = list(rows[0].keys())
        res = f"📊 ผลลัพธ์ ({result['count']} แถว):\n"
        res += " | ".join(headers) + "\n" + "-" * 40 + "\n"
        for row in rows:
            res += " | ".join(str(v) if v is not None else "-" for v in row.values()) + "\n"
        res += f"\n📝 SQL ที่ใช้: `{sql}`"
        return res

    except httpx.HTTPStatusError as e:
        err = e.response.json().get("detail", str(e))
        return f"❌ Backend Error: {err}"
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาด: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# Tool Dispatcher
# ─────────────────────────────────────────────────────────────────────────────
TOOL_MAP = {
    "search_products":           lambda c: search_products(c.get("query", "")),
    "create_preorder_ai":        lambda c: create_preorder_ai(
                                     c.get("customer_name", ""), c.get("items_json", "[]"),
                                     c.get("customer_phone", ""), c.get("company_name", "")),
    "add_product_ai":            lambda c: add_product_ai(c.get("part_name", ""), float(c.get("price", 0.0))),
    "get_preorders_ai":          lambda c: get_preorders_ai(),
    "get_order_details_ai":      lambda c: get_order_details_ai(int(c.get("order_id", 0))),
    "update_preorder_status_ai": lambda c: update_preorder_status_ai(int(c.get("order_id", 0)), c.get("status", "Approved")),
    "get_inventory_ai":          lambda c: get_inventory_ai(),
    "update_inventory_ai":       lambda c: update_inventory_ai(c.get("part_code", ""), int(c.get("quantity", 0))),
    "delete_product_ai":         lambda c: delete_product_ai(c.get("part_code", "")),
    "analyze_data_ai":           lambda c: analyze_data_ai(),
    "run_query_ai":              lambda c: run_query_ai(c.get("question", "")),
}

SYSTEM_INSTRUCTION = (
    "You are 'PartsPro AI Assistant'. You help Thai shop owners manage spare parts inventory and orders. "
    "IMPORTANT: When you need data from the system, output ONLY a raw JSON tool call — nothing else.\n\n"
    "AVAILABLE TOOLS (output exactly as shown):\n"
    '- สื่อสินค้า: {"action":"search_products","query":"..."}\n'
    '- สร้างออเดอร์: {"action":"create_preorder_ai","customer_name":"...","items_json":"[{\\"part_name\\":\\"...\\",\\"qty\\":1}]","customer_phone":"","company_name":""}\n'
    '- เพิ่มสินค้าใหม่: {"action":"add_product_ai","part_name":"...","price":0.0}\n'
    '- ดูรายการออเดอร์ทั้งหมด: {"action":"get_preorders_ai"}\n'
    '- ดูรายละเอียดออเดอร์: {"action":"get_order_details_ai","order_id":1}\n'
    '- อัพเดตสถานะออเดอร์: {"action":"update_preorder_status_ai","order_id":1,"status":"Approved"}\n'
    '- ดูสินค้าในคลัง: {"action":"get_inventory_ai"}\n'
    '- อัพเดตสต็อก: {"action":"update_inventory_ai","part_code":"SKU-001","quantity":50}\n'
    '- ลบสินค้า: {"action":"delete_product_ai","part_code":"SKU-001"}\n'
    '- วิเคราะห์ข้อมูลร้าน: {"action":"analyze_data_ai"}\n'
    '- คำถามพิเศษ (Text-to-SQL): {"action":"run_query_ai","question":"..."}\n\n'
    "RULES:\n"
    "1. Output ONLY the JSON when calling a tool — no text before or after.\n"
    '2. items_json must be a JSON string: "[{\\"part_name\\":\\"...\\",\\"qty\\":1}]"\n'
    "3. For inventory list use get_inventory_ai (not add_product_ai).\n"
    "4. For complex/custom data questions use run_query_ai.\n"
    "5. Answer in Thai after receiving RESULT."
)

# ─────────────────────────────────────────────────────────────────────────────
# Core Chat Logic
# ─────────────────────────────────────────────────────────────────────────────
def _run_chat(messages: list[dict]) -> tuple[str, str]:
    local_messages = list(messages)
    tool_used = ""

    for _ in range(3):
        formatted = [{"role": "system", "content": SYSTEM_INSTRUCTION}] + local_messages
        response = typhoon_client.chat.completions.create(
            model="typhoon-v2.5-30b-a3b-instruct",
            messages=formatted,
            temperature=0.6,
            max_tokens=512,
            top_p=0.6
        )
        ai_response = response.choices[0].message.content.strip()
        if not ai_response:
            return "รับทราบครับเจ้าของร้าน", tool_used

        json_match = re.search(r'\{\s*"action"\s*:.*?\}', ai_response, re.DOTALL)
        if json_match:
            try:
                tool_call = json.loads(json_match.group(0))
                action = tool_call.get("action")
                executor = TOOL_MAP.get(action)
                if executor:
                    tool_used = action
                    print(f">>> [Tool] Calling: {action}")
                    tool_result = executor(tool_call)
                    local_messages.append({"role": "assistant", "content": ai_response})
                    local_messages.append({"role": "user", "content": f"RESULT: {tool_result}"})
                    continue
            except Exception as e:
                print(f">>> [Tool Parse Error] {e}")

        return ai_response, tool_used

    return "ขออภัยครับ ระบบใช้เวลาประมวลผลนานเกินไป", tool_used

# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    backend_ok = False
    try:
        r = httpx.get(f"{BACKEND_API_URL}/health", timeout=3)
        backend_ok = r.status_code == 200
    except Exception:
        pass
    return {
        "status": "ok",
        "service": "agent_service",
        "port": int(os.environ.get("AGENT_PORT", 8001)),
        "backend_url": BACKEND_API_URL,
        "backend_reachable": backend_ok
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main chat endpoint.
    Request: { "messages": [...], "user_id": "..." }
    Response: { "reply": "...", "user_id": "...", "tool_used": "..." }
    """
    try:
        msg_dicts = [m.dict() for m in req.messages]
        reply, tool_used = _run_chat(msg_dicts)
    except Exception as e:
        import traceback; traceback.print_exc()
        reply = f"ขออภัยครับ ระบบ Agent ขัดข้อง (Error: {str(e)[:80]})"
        tool_used = ""

    print(f">>> [Agent] user={req.user_id} | tool={tool_used} | reply={reply[:80]}...")
    return ChatResponse(reply=reply, user_id=req.user_id, tool_used=tool_used)

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("AGENT_PORT", 8001))
    uvicorn.run("agent_service:app", host="0.0.0.0", port=port, reload=True)
