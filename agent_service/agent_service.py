"""
agent_service.py — PartsPro AI Agent Microservice (Port 8001)
=============================================================
Typhoon LLM + Manual Tool Calling แยกออกจาก backend หลัก
Backend หลัก (main.py) คุยกับ service นี้ผ่าน POST /chat
"""

import os
import sys
import re
import json
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict
from openai import OpenAI

# โหลด .env อัตโนมัติ (ถ้ามี python-dotenv ติดตั้งอยู่)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass  # ไม่มี python-dotenv ก็โหลดจาก env ที่ตั้งไว้ใน shell แทน

# ─────────────────────────────────────────────────────────────────────────────
# Path Setup — ให้ import database.py จาก ai_bill_scanner ได้
# ตั้ง env: BACKEND_PATH=../ai_bill_scanner หรือ path สัมบูรณ์
# ─────────────────────────────────────────────────────────────────────────────
BACKEND_PATH = os.environ.get("BACKEND_PATH", os.path.join(os.path.dirname(__file__), "../ai_bill_scanner"))
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

# ─────────────────────────────────────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PartsPro AI Agent Service",
    version="1.0.0",
    description="AI Agent Microservice powered by Typhoon LLM for B2B spare parts order management."
)

# Typhoon Client
typhoon_client = OpenAI(
    api_key=os.environ.get("TYPHOON_API_KEY", ""),
    base_url="https://api.opentyphoon.ai/v1"
)

# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Schema
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
    tool_used: str = ""   # ชื่อ tool ที่ถูกเรียก (ถ้ามี)

# ─────────────────────────────────────────────────────────────────────────────
# Tool Functions
# ─────────────────────────────────────────────────────────────────────────────

def search_products(query: str) -> str:
    from database import search_spare_parts_by_text
    parts = search_spare_parts_by_text(query)
    if not parts:
        return "ไม่พบสินค้าที่ตรงกับการค้นหาครับ"
    res = "รายการสินค้าที่พบ:\n"
    for p in parts:
        res += f"- [{p['part_code']}] {p['part_name']} | ราคา: {p['price']} บาท | คงเหลือ: {p['stock']} ชิ้น\n"
    return res


def create_preorder_ai(customer_name: str, items_json: str,
                       customer_phone: str = "", company_name: str = "") -> str:
    from database import create_preorder_record, search_spare_parts_by_text
    from datetime import datetime
    try:
        items = json.loads(items_json)
        total_amount = 0
        final_items = []
        for item in items:
            code, name, qty = item.get("part_code"), item.get("part_name"), item.get("qty", 1)
            parts = []
            if code:
                parts = search_spare_parts_by_text(code, limit=1)
            if not parts and name:
                parts = search_spare_parts_by_text(name, limit=1)
            if parts:
                p = parts[0]
                amount = p["price"] * qty
                total_amount += amount
                final_items.append({"part_code": p["part_code"], "part_name": p["part_name"],
                                    "quantity": qty, "unit_price": p["price"], "amount": amount})
        if not final_items:
            return "ไม่สามารถสร้างรายการได้ เนื่องจากหาข้อมูลสินค้าไม่พบครับ"
        order_id = create_preorder_record(
            customer_name=customer_name, customer_phone=customer_phone,
            company_name=company_name or "สั่งซื้อผ่าน AI",
            order_date=datetime.now().strftime("%Y-%m-%d"),
            total_amount=total_amount, items=json.dumps(final_items)
        )
        return f"สร้างรายการพรีออเดอร์สำเร็จแล้วครับ! เลขที่รายการ: PRE-{order_id:04d} ยอดรวม: ฿{total_amount:,.2f}"
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการสร้างรายการ: {str(e)}"


def add_product_ai(part_name: str, price: float) -> str:
    from database import add_spare_part
    import random
    try:
        part_code = f"AI-{random.randint(1000, 9999)}"
        add_spare_part(part_code=part_code, part_name=part_name, price=price)
        return f"เพิ่มสินค้า '{part_name}' รหัส '{part_code}' ราคา {price} บาท เรียบร้อยแล้วครับ!"
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการเพิ่มสินค้า: {str(e)}"


def get_preorders_ai() -> str:
    from database import get_all_preorders
    try:
        orders = get_all_preorders(limit=10)
        if not orders:
            return "ยังไม่มีรายการพรีออเดอร์ในขณะนี้ครับ"
        res = "รายการพรีออเดอร์ล่าสุด:\n"
        for o in orders:
            res += f"- [ID: {o['id']}] {o['customer_name']} | ยอด: ฿{o['total_amount']:,.2f} | สถานะ: {o['status']}\n"
        return res
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการดึงข้อมูล: {str(e)}"


def update_preorder_status_ai(order_id: int, status: str) -> str:
    from database import update_preorder_status
    try:
        success = update_preorder_status(order_id, status)
        return f"อัปเดตสถานะรายการ ID {order_id} เป็น '{status}' เรียบร้อยแล้วครับ!" if success \
               else f"ไม่พบรายการ ID {order_id} ในระบบครับ"
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการอัปเดต: {str(e)}"


def get_order_details_ai(order_id: int) -> str:
    from database import get_preorder_by_id
    try:
        order = get_preorder_by_id(order_id)
        if not order:
            return f"ไม่พบรายการ ID {order_id} ครับ"
        items = json.loads(order['items'])
        res = f"รายละเอียดรายการ ID {order_id} ({order['customer_name']}):\n"
        res += f"วันที่: {order['order_date']} | สถานะ: {order['status']}\nยอดรวม: ฿{order['total_amount']:,.2f}\nรายการสินค้า:\n"
        for i in items:
            res += f"- {i.get('part_name', 'N/A')} x {i.get('quantity', 0)} | ฿{i.get('amount', 0):,.2f}\n"
        return res
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการดึงข้อมูล: {str(e)}"


def get_inventory_ai() -> str:
    from database import get_all_spare_parts
    try:
        parts = get_all_spare_parts(limit=50)
        if not parts:
            return "ไม่มีสินค้าในคลังครับ"
        res = "รายการสินค้าในคลังทั้งหมด:\n"
        for p in parts:
            res += f"- [{p['part_code']}] {p['part_name']} | ราคา: ฿{p['price']:,.2f} | คงเหลือ: {p['stock']} ชิ้น\n"
        return res
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการดึงข้อมูล: {str(e)}"


def update_inventory_ai(part_code: str, quantity: int) -> str:
    from database import update_spare_part_stock
    try:
        success = update_spare_part_stock(part_code, quantity)
        return f"อัปเดตสต็อกสินค้า [{part_code}] เป็นจำนวน {quantity} ชิ้น เรียบร้อยแล้วครับ!" if success \
               else f"ไม่พบรหัสสินค้า [{part_code}] ในระบบครับ"
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการอัปเดตสต็อก: {str(e)}"


def delete_product_ai(part_code: str) -> str:
    from database import delete_spare_part
    try:
        success = delete_spare_part(part_code)
        return f"ลบสินค้า [รหัส: {part_code}] ออกจากระบบเรียบร้อยแล้วครับ!" if success \
               else f"ไม่พบรหัสสินค้า [{part_code}] ในระบบครับ"
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการลบสินค้า: {str(e)}"


def analyze_data_ai() -> str:
    from database import get_analysis_data
    try:
        data = get_analysis_data()
        res = "📊 รายงานวิเคราะห์ข้อมูลร้านค้า:\n"
        res += f"💰 ยอดขายที่อนุมัติแล้ว: ฿{data['total_sales_approved']:,.2f}\n"
        res += f"📄 บิลที่สแกนแล้ว: {data['bill_scanned_stats']['count']} ใบ (รวม ฿{data['bill_scanned_stats']['total'] or 0:,.2f})\n"
        res += "\n🏆 ลูกค้าประจำ (Top 5):\n"
        for c in data['top_customers']:
            res += f"- {c['customer_name']}: {c['count']} รายการ\n"
        res += "\n⚠️ สินค้าใกล้หมด (Stock < 5):\n"
        if data['low_stock_items']:
            for i in data['low_stock_items']:
                res += f"- {i['part_name']}: เหลือ {i['stock']} ชิ้น\n"
        else:
            res += "- ไม่มีสินค้าใกล้หมด\n"
        return res
    except Exception as e:
        return f"เกิดข้อผิดพลาดในการวิเคราะห์ข้อมูล: {str(e)}"


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
}

SYSTEM_INSTRUCTION = (
    "You are 'PartsPro AI Assistant' created by SCB 10X. You help the Shop Owner. "
    "To use tools, you MUST output a JSON object ONLY in that turn:\n"
    '- Search: {"action":"search_products","query":"..."}\n'
    '- Order: {"action":"create_preorder_ai","customer_name":"...","items_json":"...","customer_phone":"...","company_name":"..."}\n'
    '- Add Product: {"action":"add_product_ai","part_name":"...","price":...}\n'
    '- List Orders: {"action":"get_preorders_ai"}\n'
    '- Order Details: {"action":"get_order_details_ai","order_id":...}\n'
    '- Update Order: {"action":"update_preorder_status_ai","order_id":...,"status":"..."}\n'
    '- List Inventory: {"action":"get_inventory_ai"}\n'
    '- Update Inventory: {"action":"update_inventory_ai","part_code":"...","quantity":...}\n'
    '- Delete Product: {"action":"delete_product_ai","part_code":"..."}\n'
    '- Analyze Data: {"action":"analyze_data_ai"}\n'
    "Rules:\n"
    '1. items_json must be a valid JSON string: [{"part_name":"...","qty":1}]\n'
    "2. Always include customer_phone and company_name if mentioned.\n"
    "3. To list inventory, start reply with: 'รายการสินค้าในคลังทั้งหมด:'\n"
    "4. To list orders, start reply with: 'รายการพรีออเดอร์ล่าสุด:'\n"
    "5. To show order details, start reply with: 'รายละเอียดรายการ ID ...'\n"
    "Be helpful and professional. Answer in Thai."
)


# ─────────────────────────────────────────────────────────────────────────────
# Core Chat Logic
# ─────────────────────────────────────────────────────────────────────────────
def _run_chat(messages: list[dict]) -> tuple[str, str]:
    """ส่งคืน (reply_text, tool_name_used)"""
    local_messages = list(messages)
    tool_used = ""

    for _ in range(2):
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

        if '{"action":' in ai_response:
            match = re.search(r'(\{.*"action".*\})', ai_response, re.DOTALL)
            if match:
                try:
                    tool_call = json.loads(match.group(1))
                    action = tool_call.get("action")
                    executor = TOOL_MAP.get(action)
                    if executor:
                        tool_used = action
                        tool_result = executor(tool_call)
                        local_messages.append({"role": "assistant", "content": ai_response})
                        local_messages.append({"role": "user", "content": f"RESULT: {tool_result}"})
                        continue
                except Exception:
                    pass

        return ai_response, tool_used

    return "ขออภัยครับ ระบบใช้เวลาประมวลผลนานเกินไป", tool_used


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Health check — ใช้ตรวจสอบว่า service ยังทำงานอยู่"""
    return {"status": "ok", "service": "agent_service", "port": 8001}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main chat endpoint สำหรับระบบภายนอก

    Request body:
        messages  — ประวัติการสนทนา [{"role": "user"|"assistant", "content": "..."}]
        user_id   — ID ผู้ใช้ (ใช้สำหรับ logging)

    Response:
        reply     — ข้อความตอบกลับจาก AI
        user_id   — ส่งกลับมาเหมือนเดิม
        tool_used — ชื่อ tool ที่ AI เรียกใช้ (ถ้ามี เช่น "search_products")
    """
    try:
        msg_dicts = [m.dict() for m in req.messages]
        reply, tool_used = _run_chat(msg_dicts)
    except Exception as e:
        import traceback
        traceback.print_exc()
        reply = f"ขออภัยครับ ระบบ Agent ขัดข้อง (Error: {str(e)[:80]})"
        tool_used = ""

    print(f">>> [Agent] user={req.user_id} | tool={tool_used} | reply={reply[:80]}...")
    return ChatResponse(reply=reply, user_id=req.user_id, tool_used=tool_used)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("AGENT_PORT", 8001))
    uvicorn.run("agent_service:app", host="0.0.0.0", port=port, reload=True)
