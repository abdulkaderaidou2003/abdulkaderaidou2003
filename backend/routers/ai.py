"""AI Command Center: chat (SSE), history, daily ops brief."""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from core.db import db, EMERGENT_LLM_KEY
from core.deps import get_user_from_token, now_utc
from core.models import ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter()

ASSISTANT_SYSTEM_PROMPTS = {
    "hr": "You are Aidou's AI HR Assistant. Help with employee records, recruiting, onboarding, leave, performance reviews, and Canadian employment standards. Be concise and actionable.",
    "accountant": "You are Aidou's AI Accountant. Help with AP/AR, general ledger, HST/GST, payroll taxes, Canadian corporate tax, budgeting and forecasting. Be precise with numbers.",
    "scheduler": "You are Aidou's AI Scheduler. Help with workforce shift planning, attendance, time-off, union seniority rules, and capacity optimization. Be operational.",
    "support": "You are Aidou's AI Customer Support specialist. Help draft replies, summarize tickets, and resolve customer issues with empathy and brevity.",
    "marketing": "You are Aidou's AI Marketing Assistant. Help craft campaigns, social posts, email copy, promotions and review responses. Be on-brand and concise.",
    "analytics": "You are Aidou's AI Analytics Assistant. Help interpret KPIs, build executive summaries, and propose data-driven actions.",
    "advisor": "You are Aidou's AI Business Advisor. Provide strategic advice across HR, finance, ops and compliance for Canadian SMB to enterprise. Be pragmatic and senior in tone.",
}


@router.post("/ai/chat")
async def ai_chat(body: ChatRequest, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    assistant = body.assistant if body.assistant in ASSISTANT_SYSTEM_PROMPTS else "advisor"
    system = ASSISTANT_SYSTEM_PROMPTS[assistant]

    await db.ai_messages.insert_one({
        "session_id": body.session_id,
        "user_id": user["user_id"],
        "assistant": assistant,
        "role": "user",
        "content": body.message,
        "created_at": now_utc(),
    })

    async def event_generator():
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        except Exception as e:
            yield f"data: [error] LLM lib unavailable: {e}\n\n"
            return

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"{user['user_id']}:{assistant}:{body.session_id}",
            system_message=system,
        ).with_model("openai", "gpt-5.2")

        full_text = ""
        try:
            async for event in chat.stream_message(UserMessage(text=body.message)):
                if isinstance(event, TextDelta):
                    full_text += event.content
                    yield f"data: {event.content}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:
            yield f"data: [error] {str(e)}\n\n"
            return

        await db.ai_messages.insert_one({
            "session_id": body.session_id,
            "user_id": user["user_id"],
            "assistant": assistant,
            "role": "assistant",
            "content": full_text,
            "created_at": now_utc(),
        })
        yield "data: [done]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/ai/history")
async def ai_history(session_id: str, assistant: str, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    msgs = await db.ai_messages.find(
        {"session_id": session_id, "assistant": assistant, "user_id": user["user_id"]},
        {"_id": 0},
    ).sort("created_at", 1).to_list(500)
    for m in msgs:
        if isinstance(m.get("created_at"), datetime):
            m["created_at"] = m["created_at"].isoformat()
    return {"messages": msgs}


@router.get("/ai/ops-brief")
async def ops_brief(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    cache_key = f"ops_brief:{co_id}"
    cached = await db.cache.find_one({"key": cache_key}, {"_id": 0})
    if cached:
        fetched_at = cached.get("fetched_at")
        if isinstance(fetched_at, datetime):
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if (now_utc() - fetched_at).total_seconds() < 3600:
                return {"brief": cached["brief"], "metrics": cached["metrics"], "cached": True}

    revenue_today = 0.0
    sales = await db.sales.find({"company_id": co_id}, {"_id": 0}).to_list(200)
    today_iso = now_utc().date().isoformat()
    for s in sales:
        created = s.get("created_at")
        if isinstance(created, datetime) and created.date().isoformat() == today_iso:
            revenue_today += float(s.get("total", 0))

    open_tickets = await db.tickets.count_documents({"company_id": co_id, "status": {"$in": ["open", "in_progress"]}})
    high_pri = await db.tickets.count_documents({"company_id": co_id, "priority": "high", "status": {"$ne": "closed"}})
    emps_active = await db.employees.count_documents({"company_id": co_id, "status": "active"})
    vehs = await db.vehicles.find({"company_id": co_id}, {"_id": 0, "status": 1, "fuel_pct": 1}).to_list(50)
    veh_active = sum(1 for v in vehs if v.get("status") == "active")
    low_fuel = sum(1 for v in vehs if v.get("fuel_pct", 100) < 30)
    inv = await db.inventory.find({"company_id": co_id}, {"_id": 0, "stock": 1, "reorder_at": 1}).to_list(500)
    low_stock = sum(1 for it in inv if it.get("stock", 0) <= it.get("reorder_at", 0))
    alerts_unread = await db.alerts.count_documents({"company_id": co_id, "read": False})
    company = await db.companies.find_one({"company_id": co_id}, {"_id": 0})
    co_name = company.get("name") if company else "this company"

    metrics = {
        "company": co_name,
        "date": today_iso,
        "pos_revenue_today": round(revenue_today, 2),
        "open_tickets": open_tickets,
        "high_priority_tickets": high_pri,
        "active_employees": emps_active,
        "fleet_active": veh_active,
        "fleet_total": len(vehs),
        "fleet_low_fuel": low_fuel,
        "inventory_low_stock": low_stock,
        "alerts_unread": alerts_unread,
    }

    prompt = (
        "You are Aidou's AI Business Advisor. Write a single concise paragraph (max 60 words) "
        "as a Daily Ops Brief for an executive opening their app today. Reference the most "
        "important live numbers and end with one specific action recommendation. Do not list bullets. "
        f"Metrics JSON: {json.dumps(metrics)}"
    )

    brief_text = ""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"ops-brief:{co_id}:{today_iso}",
            system_message="You are a senior operations advisor. Be brief and decisive.",
        ).with_model("openai", "gpt-5.2")
        resp = await chat.send_message(UserMessage(text=prompt))
        brief_text = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
    except Exception as e:
        logger.warning(f"ops_brief LLM failed: {e}")
        brief_text = (
            f"{co_name} has {open_tickets} open tickets ({high_pri} high priority), "
            f"{veh_active}/{len(vehs)} vehicles active, {low_stock} items below reorder, "
            f"and {alerts_unread} unread alerts. Recommend triaging the high-priority tickets first."
        )

    await db.cache.update_one(
        {"key": cache_key},
        {"$set": {
            "key": cache_key,
            "brief": brief_text,
            "metrics": metrics,
            "fetched_at": now_utc(),
        }},
        upsert=True,
    )
    return {"brief": brief_text, "metrics": metrics, "cached": False}
