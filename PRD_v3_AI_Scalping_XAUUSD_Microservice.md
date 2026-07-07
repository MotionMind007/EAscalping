# PRD v3 --- AI Scalping XAUUSD Platform (Microservice)

## Vision

Membangun platform algorithmic trading XAUUSD yang modular, scalable,
dan production-ready. EA hanya bertugas sebagai executor, seluruh
business logic berada di backend.

## Architecture

``` text
                         Internet
                             │
                     MT5 Terminal + EA
                             │
                    HTTP/WebSocket
                             │
                    API Gateway (FastAPI)
                             │
 ┌───────────────┬───────────────┬───────────────┐
 │               │               │               │
Market      Signal Engine    Risk Engine   News Service
Data
 │               │               │
 └───────────────┴───────────────┘
                 │
          AI Prediction Service
                 │
          Trade Orchestrator
                 │
         Position Manager
                 │
      PostgreSQL + Redis
                 │
 Monitoring / Grafana / Alerts
```

## Core Services

-   EA Gateway
-   Market Data Service
-   Signal Engine
-   AI Prediction Service
-   Risk Engine
-   Trade Orchestrator
-   Position Manager
-   News Service
-   Monitoring Service

## Trading Rules

### Session

-   Trading hanya pada sesi London & New York.
-   Di luar sesi: Monitoring Only.
-   EA tetap hidup 24/7.

### Daily Loss

-   Maksimum 3% dari equity awal hari.
-   Jika tercapai:
    -   Masuk mode RISK_LOCK.
    -   Tidak membuka posisi baru.
    -   Reset otomatis pada hari trading berikutnya.

### Position Rules

-   Maksimal 1 posisi terbuka.
-   Tanpa Martingale.
-   Tanpa Grid.
-   Tanpa Hedging.

## State Machine

``` text
BOOT
 ↓
CONNECT
 ↓
WAIT_SESSION
 ↓
CHECK_RISK
 ↓
SCAN_SIGNAL
 ↓
AI_CONFIRMATION
 ↓
OPEN_POSITION
 ↓
MANAGE_POSITION
 ↓
POSITION_CLOSED
 ↓
WAIT_SESSION
```

## Tech Stack

  Layer           Technology
  --------------- -----------------------------
  EA              MQL5
  Backend         Python
  API             FastAPI
  AI              XGBoost / LightGBM
  Cache           Redis
  Database        PostgreSQL
  Monitoring      Prometheus + Grafana + Loki
  Reverse Proxy   Nginx
  Container       Docker
  VPS             Ubuntu 24.04

## Roadmap

1.  EA Gateway
2.  Market Data
3.  Execution Engine
4.  Risk Engine
5.  AI Prediction
6.  Dashboard & Monitoring
7.  Backtesting
8.  Forward Test
9.  Production

## Repository Structure

``` text
docs/
├── 01-Executive-Summary.md
├── 02-Business-Requirements.md
├── 03-Product-Requirements.md
├── 04-System-Architecture.md
├── 05-Microservices.md
├── 06-Domain-Driven-Design.md
├── 07-API-Specification.md
├── 08-Database-Design.md
├── 09-AI-Engine.md
├── 10-Trading-Engine.md
├── 11-Risk-Engine.md
├── 12-Execution-Engine.md
├── 13-Monitoring.md
├── 14-Deployment.md
├── 15-Testing.md
└── 16-Roadmap.md
```
