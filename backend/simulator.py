import random
import math
import time
from typing import Dict, List

class MarketSimulator:
    def __init__(self):
        # Initial prices for default tickers
        self.prices = {
            "AAPL": 190.0,
            "GOOGL": 175.0,
            "MSFT": 420.0,
            "AMZN": 180.0,
            "TSLA": 170.0,
            "NVDA": 900.0,
            "META": 500.0,
            "JPM": 195.0,
            "V": 280.0,
            "NFLX": 620.0
        }
        self.prev_prices = self.prices.copy()
        # Simulation parameters: dt (time step), mu (drift), sigma (volatility)
        self.dt = 0.01  # Small time step
        self.params = {ticker: {"mu": 0.0001, "sigma": 0.01} for ticker in self.prices}

    def update_prices(self):
        self.prev_prices = self.prices.copy()
        for ticker in self.prices:
            mu = self.params[ticker]["mu"]
            sigma = self.params[ticker]["sigma"]
            
            # Geometric Brownian Motion formula:
            # S(t+dt) = S(t) * exp((mu - 0.5 * sigma^2) * dt + sigma * sqrt(dt) * epsilon)
            epsilon = random.gauss(0, 1)
            change_pct = math.exp((mu - 0.5 * sigma**2) * self.dt + sigma * math.sqrt(self.dt) * epsilon)
            
            self.prices[ticker] *= change_pct
            
            # Occasional random "events" (0.5% chance per update)
            if random.random() < 0.005:
                event_move = random.uniform(-0.05, 0.05)
                self.prices[ticker] *= (1 + event_move)

    def get_latest(self) -> List[Dict]:
        updates = []
        for ticker, price in self.prices.items():
            prev = self.prev_prices[ticker]
            direction = "up" if price >= prev else "down"
            updates.append({
                "ticker": ticker,
                "price": round(price, 2),
                "prev_price": round(prev, 2),
                "change_pct": round(((price - prev) / prev) * 100, 4),
                "direction": direction,
                "timestamp": time.time()
            })
        return updates

if __name__ == "__main__":
    sim = MarketSimulator()
    for _ in range(5):
        sim.update_prices()
        print(sim.get_latest()[0]) # Print AAPL update
        time.sleep(0.5)
