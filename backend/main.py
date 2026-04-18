import asyncio
import json
import time
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from simulator import MarketSimulator
from database import init_db, get_db_connection
from llm import get_ai_response

app = FastAPI(title="FinAlly API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global price simulator
simulator = MarketSimulator()

@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(run_simulator())
    asyncio.create_task(record_portfolio_snapshots())

async def run_simulator():
    while True:
        simulator.update_prices()
        await asyncio.sleep(0.5)

async def record_portfolio_snapshots():
    """Record portfolio value every 30 seconds."""
    while True:
        await take_snapshot()
        await asyncio.sleep(30)

async def take_snapshot():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate total value
    cursor.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'")
    cash = cursor.fetchone()["cash_balance"]
    cursor.execute("SELECT ticker, quantity FROM positions WHERE user_id = 'default'")
    positions = cursor.fetchall()
    
    total_value = cash
    for pos in positions:
        total_value += pos["quantity"] * simulator.prices.get(pos["ticker"], 0)
    
    cursor.execute("INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
                   (str(uuid.uuid4()), "default", total_value, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# --- System Endpoints ---

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# --- Frontend Serving ---

@app.get("/")
async def read_index():
    return FileResponse("../frontend/index.html")

# --- SSE Streaming ---

@app.get("/api/stream/prices")
async def stream_prices(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            data = simulator.get_latest()
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Portfolio Endpoints ---

@app.get("/api/portfolio")
async def get_portfolio():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'")
    profile = cursor.fetchone()
    cash = profile["cash_balance"] if profile else 0
    cursor.execute("SELECT * FROM positions WHERE user_id = 'default'")
    positions = [dict(row) for row in cursor.fetchall()]
    
    total_value = cash
    for pos in positions:
        current_price = simulator.prices.get(pos["ticker"], pos["avg_cost"])
        pos["current_price"] = current_price
        pos["market_value"] = pos["quantity"] * current_price
        pos["unrealized_pnl"] = pos["market_value"] - (pos["quantity"] * pos["avg_cost"])
        pos["pnl_pct"] = (pos["unrealized_pnl"] / (pos["quantity"] * pos["avg_cost"]) * 100) if pos["quantity"] > 0 else 0
        total_value += pos["market_value"]
    
    conn.close()
    return {"cash_balance": cash, "total_value": total_value, "positions": positions}

class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str

@app.post("/api/portfolio/trade")
async def execute_trade(trade: TradeRequest):
    result = await process_trade(trade.ticker, trade.quantity, trade.side)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await take_snapshot()
    return result

async def process_trade(ticker: str, qty: float, side: str):
    ticker = ticker.upper()
    side = side.lower()
    price = simulator.prices.get(ticker, 0)
    if price == 0: return {"error": "Invalid ticker or price unavailable"}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'")
    cash = cursor.fetchone()["cash_balance"]
    cost = qty * price
    
    if side == "buy":
        if cash < cost: return {"error": "Insufficient funds"}
        cursor.execute("UPDATE users_profile SET cash_balance = cash_balance - ? WHERE id = 'default'", (cost,))
        cursor.execute("SELECT * FROM positions WHERE user_id = 'default' AND ticker = ?", (ticker,))
        pos = cursor.fetchone()
        if pos:
            new_qty = pos["quantity"] + qty
            new_avg_cost = ((pos["quantity"] * pos["avg_cost"]) + cost) / new_qty
            cursor.execute("UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE id = ?", (new_qty, new_avg_cost, datetime.now().isoformat(), pos["id"]))
        else:
            cursor.execute("INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), "default", ticker, qty, price, datetime.now().isoformat()))
    elif side == "sell":
        cursor.execute("SELECT * FROM positions WHERE user_id = 'default' AND ticker = ?", (ticker,))
        pos = cursor.fetchone()
        if not pos or pos["quantity"] < qty: return {"error": "Insufficient shares"}
        cursor.execute("UPDATE users_profile SET cash_balance = cash_balance + ? WHERE id = 'default'", (cost,))
        new_qty = pos["quantity"] - qty
        if new_qty == 0: cursor.execute("DELETE FROM positions WHERE id = ?", (pos["id"],))
        else: cursor.execute("UPDATE positions SET quantity = ?, updated_at = ? WHERE id = ?", (new_qty, datetime.now().isoformat(), pos["id"]))
    
    cursor.execute("INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), "default", ticker, side, qty, price, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {"success": True, "executed_price": price, "ticker": ticker, "side": side, "quantity": qty}

@app.get("/api/portfolio/history")
async def get_portfolio_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id = 'default' ORDER BY recorded_at ASC")
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history

# --- Watchlist Endpoints ---

@app.get("/api/watchlist")
async def get_watchlist():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM watchlist WHERE user_id = 'default'")
    tickers = [row["ticker"] for row in cursor.fetchall()]
    conn.close()
    return [{"ticker": t, "price": simulator.prices.get(t, 0), "prev_price": simulator.prev_prices.get(t, 0)} for t in tickers]

class WatchlistRequest(BaseModel):
    ticker: str

@app.post("/api/watchlist")
async def add_to_watchlist(req: WatchlistRequest):
    ticker = req.ticker.upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                       (str(uuid.uuid4()), "default", ticker, datetime.now().isoformat()))
        conn.commit()
    except: pass # Already exists
    conn.close()
    return {"success": True}

@app.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str):
    ticker = ticker.upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE user_id = 'default' AND ticker = ?", (ticker,))
    conn.commit()
    conn.close()
    return {"success": True}

# --- AI Chat Endpoint ---

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat(req: ChatRequest):
    # 1. Get Context
    portfolio = await get_portfolio()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_messages WHERE user_id = 'default' ORDER BY created_at ASC LIMIT 10")
    history = [dict(row) for row in cursor.fetchall()]
    
    # 2. Get AI Response
    ai_resp = await get_ai_response(req.message, portfolio, history)
    
    # 3. Execute Actions
    executed_trades = []
    if "trades" in ai_resp and ai_resp["trades"]:
        for t in ai_resp["trades"]:
            res = await process_trade(t["ticker"], t["quantity"], t["side"])
            executed_trades.append(res)
            
    if "watchlist_changes" in ai_resp and ai_resp["watchlist_changes"]:
        for wc in ai_resp["watchlist_changes"]:
            if wc["action"] == "add":
                await add_to_watchlist(WatchlistRequest(ticker=wc["ticker"]))
            elif wc["action"] == "remove":
                await remove_from_watchlist(wc["ticker"])

    # 4. Store Messages
    cursor.execute("INSERT INTO chat_messages (id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                   (str(uuid.uuid4()), "default", "user", req.message, datetime.now().isoformat()))
    cursor.execute("INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (str(uuid.uuid4()), "default", "assistant", ai_resp["message"], json.dumps(ai_resp.get("trades", [])), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return {
        "message": ai_resp["message"],
        "executed_trades": executed_trades,
        "watchlist_changes": ai_resp.get("watchlist_changes", [])
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
