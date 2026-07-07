# PRD --- AI Scalping XAUUSD (Microservice Architecture)

## 1. Vision

Membangun platform trading otomatis XAUUSD yang modular, scalable, dan
production-ready.

## Goals

-   Win Rate \> 60%
-   Profit Factor \> 1.8
-   Max Drawdown \< 10%
-   Risk/trade: 0.5--1%

## Microservice Architecture

``` text
                 MT5 Terminal
                      │
                Expert Advisor
                      │ HTTP/WebSocket
        ┌─────────────┴─────────────┐
        │                           │
 Signal Service              Risk Service
        │                           │
        ├─────────────┬─────────────┤
        │             │             │
 AI Prediction   Market Data   News Filter
        │             │             │
        └───────┬─────┴─────────────┘
                │
          Trade Orchestrator
                │
        Execution / Position Manager
                │
         SQLite / PostgreSQL
                │
 Dashboard / Metrics / Alerts
```

## Services

### 1. EA Gateway

-   Mengambil tick & candle dari MT5
-   Mengirim data ke backend
-   Eksekusi BUY/SELL/CLOSE

### 2. Market Data Service

-   OHLC
-   Tick
-   Spread
-   ATR
-   EMA
-   RSI
-   MACD
-   ADX

### 3. AI Prediction Service

Input: - 100 candle terakhir - EMA20/50/200 - ATR - RSI - MACD - ADX -
Volume - Spread - Session

Output: - BUY - SELL - HOLD - Confidence

### 4. Signal Service

-   Validasi tren
-   Pullback
-   Breakout
-   Konfirmasi AI

### 5. Risk Service

-   Lot sizing
-   SL/TP
-   Break-even
-   Trailing stop
-   Daily loss limit
-   Daily profit target

### 6. News Filter

-   High-impact news
-   Stop trading ±30 menit

### 7. Trade Orchestrator

-   Koordinasi seluruh service
-   Mencegah order ganda
-   Logging

### 8. Dashboard

-   Balance
-   Equity
-   Floating P/L
-   Win rate
-   Drawdown
-   AI confidence
-   Spread
-   Status bot

## API

### POST /predict

Mengembalikan sinyal AI.

### POST /trade/open

Membuka posisi.

### POST /trade/close

Menutup posisi.

### GET /health

Health check.

### GET /metrics

Statistik bot.

## Folder Structure

``` text
ai-scalping/
├── gateway/
├── services/
│   ├── ai/
│   ├── signal/
│   ├── risk/
│   ├── market-data/
│   ├── news/
│   └── trade/
├── dashboard/
├── database/
├── docs/
├── tests/
├── docker/
└── monitoring/
```

## Tech Stack

-   MT5 EA: MQL5
-   Backend: Python + FastAPI
-   AI: XGBoost / LightGBM
-   Queue: Redis
-   Database: PostgreSQL (SQLite untuk dev)
-   Monitoring: Prometheus + Grafana
-   Logs: Loki
-   Containers: Docker
-   Reverse Proxy: Nginx
-   VPS: Ubuntu 24.04 LTS

## Deployment

-   Docker Compose untuk single VPS.
-   Pisahkan service agar mudah diskalakan.
-   CI/CD untuk deployment otomatis.

## Development Roadmap

1.  EA Gateway
2.  Market Data
3.  Risk Engine
4.  Signal Engine
5.  AI Prediction
6.  Dashboard
7.  Monitoring & Alerts
8.  Backtest
9.  Forward Test (Demo)
10. Production

## Trading Session Rules (Updated)

### Active Trading Window

-   Trading hanya pada sesi London dan New York.
-   Di luar sesi tersebut, EA tetap berjalan tetapi **tidak membuka
    posisi baru**.

### Session Behavior

-   EA tetap aktif 24/7 untuk monitoring.
-   Saat sesi dimulai, EA otomatis mengaktifkan proses pencarian sinyal.
-   Saat sesi berakhir, EA menghentikan pembukaan posisi baru dan masuk
    ke mode monitoring.

### Daily Risk Control

-   Maksimum kerugian harian: **3% dari equity awal hari**.
-   Jika daily loss mencapai 3%:
    -   Tidak membuka posisi baru.
    -   Tetap memonitor pasar.
    -   Trading dilanjutkan otomatis pada hari trading berikutnya
        setelah reset harian.

### State Machine

``` text
MONITORING
    │
    ├── Session Open ──► TRADING
    │                        │
    │                        ├── Daily Loss >=3% ─► RISK_LOCK
    │                        └── Session End ─────► MONITORING
    │
    └──────── Next Trading Day ───────────────► TRADING
```
