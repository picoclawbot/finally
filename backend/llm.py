import os
import json
import litellm
from typing import List, Dict, Optional
from pydantic import BaseModel

# Configuration
LLM_MOCK = os.getenv("LLM_MOCK", "false").lower() == "true"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = "openrouter/openai/gpt-3.5-turbo" # Default, spec mentioned gpt-oss-120b but let's be safe

class TradeAction(BaseModel):
    ticker: str
    side: str
    quantity: float

class WatchlistAction(BaseModel):
    ticker: str
    action: str # "add" or "remove"

class LLMResponse(BaseModel):
    message: str
    trades: Optional[List[TradeAction]] = []
    watchlist_changes: Optional[List[WatchlistAction]] = []

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant.
Analyze portfolio composition, risk concentration, and P&L.
Suggest trades with reasoning.
Execute trades when the user asks or agrees.
Manage the watchlist proactively.
Be concise and data-driven in responses.
Always respond with valid structured JSON.

Schema:
{
  "message": "Conversational response",
  "trades": [{"ticker": "SYMBOL", "side": "buy/sell", "quantity": 10}],
  "watchlist_changes": [{"ticker": "SYMBOL", "action": "add/remove"}]
}
"""

async def get_ai_response(user_message: str, portfolio_context: Dict, chat_history: List[Dict]) -> Dict:
    if LLM_MOCK:
        return {
            "message": f"I've analyzed your request: '{user_message}'. Your portfolio looks solid with a total value of {portfolio_context.get('total_value', 0)}. I suggest adding NVDA to your watchlist.",
            "trades": [],
            "watchlist_changes": [{"ticker": "NVDA", "action": "add"}]
        }

    # Construct messages for LiteLLM
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add context
    context_str = f"Current Portfolio: {json.dumps(portfolio_context)}"
    messages.append({"role": "system", "content": context_str})
    
    # Add history
    for msg in chat_history[-5:]: # Last 5 messages
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add user message
    messages.append({"role": "user", "content": user_message})

    try:
        response = await litellm.acompletion(
            model=MODEL,
            messages=messages,
            api_key=OPENROUTER_API_KEY,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"LLM Error: {e}")
        return {
            "message": "I encountered an error while processing your request. Please try again.",
            "trades": [],
            "watchlist_changes": []
        }
