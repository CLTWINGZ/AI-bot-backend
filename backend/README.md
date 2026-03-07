# 🚀 CryptoInsight Alpha v2

A high-frequency quantitative crypto analysis dashboard and AI advisor. Built with **FastAPI**, **React (Vite)**, and advanced technical analysis engines.

---

## 🏗️ Architecture
- **Frontend**: React 19, Framer Motion, Tailwind-ready CSS, TradingView Widgets.
- **Backend**: FastAPI, PatternBot (SMC/ICT Engine), Multi-horizon Forecasting.
- **Data**: Real-time Binance API integration via WebSockets.

---

## 🛠️ Local Development Setup

To run the full stack on `localhost`, follow these steps:

### 1. 🐍 Backend Setup (API)
Open a terminal in the project root:
```bash
# Enter backend directory
cd backend

# Create and activate virtual environment (Windows)
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API will be available at: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`

### 2. ⚛️ Frontend Setup (UI)
Open a **new** terminal in the project root:
```bash
# Enter frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```
The Dashboard will be available at: `http://localhost:5173`

---

## 🐳 Docker Setup (Alternative)
If you have Docker Desktop running:
```bash
docker-compose up -d --build
```

---

## 📊 Features & Chat Triggers
The AI Advisor recognizes advanced quantitative intents:
- **"What is the next day forecast for BTC?"** -> Triggers Probabilistic Forecast.
- **"Show me ICT concepts and RSI divergence"** -> Triggers SMC/ICT Chart Engine.
- **"Run MACD backtest for ETH"** -> Triggers Multi-Timeframe Strategy Tester.
- **"Autopilot"** -> Enable/Disable the 60-second automated signal stream.

---

## ⚙️ Configuration
The app will prompt you for a **Gemini API Key** on first load. 
Alternatively, create a `backend/.env` file:
```env
GEMINI_API_KEY=your_key_here
LLM_MODEL=gemini-1.5-flash
```

---
*⚠️ Disclaimer: Not financial advice. Projections are probabilistic.*
