//+------------------------------------------------------------------+
//|                                                  EAGateway.mq5    |
//|                         EA Gateway - Main Expert Advisor           |
//|                         Bridges MT5 Terminal and Python Backend     |
//+------------------------------------------------------------------+
#property copyright "MotionMind"
#property link      ""
#property version   "1.00"
#property strict

//+------------------------------------------------------------------+
//| Include all modules                                                |
//+------------------------------------------------------------------+
#include <EAGateway\\Types.mqh>
#include <EAGateway\\Inputs.mqh>
#include <EAGateway\\ConfigManager.mqh>
#include <EAGateway\\Logger.mqh>
#include <EAGateway\\StateMachine.mqh>
#include <EAGateway\\HttpClient.mqh>
#include <EAGateway\\MarketCollector.mqh>
#include <EAGateway\\TradeExecutor.mqh>
#include <EAGateway\\HealthMonitor.mqh>
#include <EAGateway\\SessionManager.mqh>
#include <EAGateway\\RecoveryManager.mqh>
#include <EAGateway\\SessionAbortHandler.mqh>
#include <EAGateway\\CommandDispatcher.mqh>

//+------------------------------------------------------------------+
//| Global state - defined AFTER includes so EAState type is known     |
//+------------------------------------------------------------------+
EAState g_currentState = STATE_BOOT;

//+------------------------------------------------------------------+
//| Constants                                                          |
//+------------------------------------------------------------------+
#define HEARTBEAT_ENDPOINT         "/api/v1/health/heartbeat"
#define POSITION_STATUS_ENDPOINT   "/api/v1/position/status"
#define STATE_TRANSITION_ENDPOINT  "/api/v1/state/transition"
#define SESSION_CHECK_INTERVAL_SEC 60
#define ORPHAN_CHECK_INTERVAL_SEC  60
#define POSITION_REPORT_SEC        5
#define MT5_CONNECTIVITY_SEC       1
#define SIGNAL_SCAN_INTERVAL_SEC   3    // Poll backend for signal every 3s

//+------------------------------------------------------------------+
//| Global module pointers (heap allocated)                            |
//+------------------------------------------------------------------+
CConfigManager*       g_configManager    = NULL;
CLogger*              g_logger           = NULL;
CStateMachine*        g_stateMachine     = NULL;
CHttpClient*          g_httpClient       = NULL;
CMarketCollector*     g_marketCollector  = NULL;
CTradeExecutor*       g_tradeExecutor    = NULL;
CHealthMonitor*       g_healthMonitor    = NULL;
CSessionManager*      g_sessionManager   = NULL;
CRecoveryManager*     g_recoveryManager  = NULL;
CSessionAbortHandler* g_sessionAbortHandler = NULL;
CCommandDispatcher*   g_commandDispatcher = NULL;

//+------------------------------------------------------------------+
//| Timer counters (1-second resolution, track elapsed seconds)       |
//+------------------------------------------------------------------+
int g_heartbeatCounter       = 0;
int g_sessionCheckCounter    = 0;
int g_orphanCheckCounter     = 0;
int g_positionReportCounter  = 0;
int g_signalScanCounter      = 0;

//+------------------------------------------------------------------+
//| New bar detection                                                  |
//+------------------------------------------------------------------+
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
//| Helper: Convert timeframe string to ENUM_TIMEFRAMES                |
//+------------------------------------------------------------------+
ENUM_TIMEFRAMES StringToTimeframe(string tf)
{
    if(tf == "M1")  return PERIOD_M1;
    if(tf == "M5")  return PERIOD_M5;
    if(tf == "M15") return PERIOD_M15;
    if(tf == "H1")  return PERIOD_H1;
    return PERIOD_M1;
}

//+------------------------------------------------------------------+
//| Helper: Sync g_currentState from StateMachine                     |
//+------------------------------------------------------------------+
void SyncCurrentState()
{
    if(g_stateMachine != NULL)
        g_currentState = g_stateMachine.GetCurrentState();
}

//+------------------------------------------------------------------+
//| Helper: Build position status JSON payload                        |
//+------------------------------------------------------------------+
string BuildPositionStatusJson()
{
    if(!PositionSelect(Symbol()))
        return "";

    long     ticket      = (long)PositionGetInteger(POSITION_TICKET);
    long     posType     = PositionGetInteger(POSITION_TYPE);
    string   direction   = (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL";
    double   lotSize     = PositionGetDouble(POSITION_VOLUME);
    double   openPrice   = PositionGetDouble(POSITION_PRICE_OPEN);
    double   currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
    double   unrealizedPnl = PositionGetDouble(POSITION_PROFIT);

    // Format timestamp
    datetime now = TimeGMT();
    MqlDateTime dt;
    TimeToStruct(now, dt);
    int ms = (int)(GetTickCount() % 1000);
    string timestamp = StringFormat("%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
                                   dt.year, dt.mon, dt.day,
                                   dt.hour, dt.min, dt.sec, ms);

    string json = "{";
    json += "\"ticket\":" + IntegerToString(ticket) + ",";
    json += "\"symbol\":\"" + Symbol() + "\",";
    json += "\"direction\":\"" + direction + "\",";
    json += "\"lot_size\":" + DoubleToString(lotSize, 2) + ",";
    json += "\"open_price\":" + DoubleToString(openPrice, 2) + ",";
    json += "\"current_price\":" + DoubleToString(currentPrice, 2) + ",";
    json += "\"unrealized_pnl\":" + DoubleToString(unrealizedPnl, 2) + ",";
    json += "\"timestamp\":\"" + timestamp + "\"";
    json += "}";

    return json;
}

//+------------------------------------------------------------------+
//| Helper: Build state transition request JSON                       |
//+------------------------------------------------------------------+
string BuildTransitionJson(EAState currentState, EAState requestedState, string reason)
{
    // Format timestamp
    datetime now = TimeGMT();
    MqlDateTime dt;
    TimeToStruct(now, dt);
    int ms = (int)(GetTickCount() % 1000);
    string timestamp = StringFormat("%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
                                   dt.year, dt.mon, dt.day,
                                   dt.hour, dt.min, dt.sec, ms);

    // Get state strings from StateMachine
    string currentStateStr  = g_stateMachine.StateToString(currentState);
    string requestedStateStr = g_stateMachine.StateToString(requestedState);

    string json = "{";
    json += "\"current_state\":\"" + currentStateStr + "\",";
    json += "\"requested_state\":\"" + requestedStateStr + "\",";
    json += "\"reason\":\"" + reason + "\",";
    json += "\"timestamp\":\"" + timestamp + "\"";
    json += "}";

    return json;
}

//+------------------------------------------------------------------+
//| Helper: Request state transition from backend                     |
//| POSTs to /api/v1/state/transition and processes response          |
//| Returns true if transition was approved by backend                |
//+------------------------------------------------------------------+
bool RequestBackendTransition(EAState currentState, EAState requestedState, string reason)
{
    if(g_httpClient == NULL || g_commandDispatcher == NULL)
    {
        if(g_logger != NULL)
            g_logger.Error("EAGateway", "Cannot request transition: HttpClient or CommandDispatcher is NULL");
        return false;
    }

    string json = BuildTransitionJson(currentState, requestedState, reason);

    if(g_logger != NULL)
    {
        string fromStr = g_stateMachine.StateToString(currentState);
        string toStr   = g_stateMachine.StateToString(requestedState);
        g_logger.Info("EAGateway", "Requesting transition: " + fromStr + " -> " + toStr);
    }

    HttpResponse response = g_httpClient.Post(STATE_TRANSITION_ENDPOINT, json);

    if(response.statusCode < 200 || response.statusCode >= 300)
    {
        if(g_logger != NULL)
            g_logger.Warn("EAGateway", "Transition request failed. HTTP " +
                         IntegerToString(response.statusCode));
        return false;
    }

    // Pass response to CommandDispatcher (handles approval + embedded commands)
    g_commandDispatcher.HandleStateResponse(response.body);
    SyncCurrentState();

    // Check if we actually transitioned to the requested state
    EAState newState = g_stateMachine.GetCurrentState();
    return (newState == requestedState);
}

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    //--- Step 1: Create ConfigManager and validate inputs
    g_configManager = new CConfigManager();
    if(!g_configManager.LoadAndValidate())
    {
        Print("[EAGateway] Configuration validation failed: " + g_configManager.GetValidationError());
        // Remain in BOOT state on validation failure
        return(INIT_SUCCEEDED);
    }

    //--- Step 2: Create Logger and initialize
    g_logger = new CLogger();
    if(!g_logger.Init("EAGateway"))
    {
        Print("[EAGateway] Logger initialization failed");
        return(INIT_SUCCEEDED);
    }
    g_logger.Info("EAGateway", "Configuration validated successfully. Starting initialization...");

    //--- Step 3: Create all module instances
    g_stateMachine        = new CStateMachine(g_logger);
    g_httpClient          = new CHttpClient();
    g_marketCollector     = new CMarketCollector();
    g_tradeExecutor       = new CTradeExecutor();
    g_healthMonitor       = new CHealthMonitor();
    g_sessionManager      = new CSessionManager();
    g_recoveryManager     = new CRecoveryManager();
    g_sessionAbortHandler = new CSessionAbortHandler();

    //--- Step 4: Initialize each module with its dependencies
    // HttpClient
    g_httpClient.Init(g_logger);
    g_httpClient.SetBaseUrl(g_configManager.GetBackendUrl());
    g_httpClient.SetAuthToken(g_configManager.GetAuthToken());
    g_httpClient.SetTimeout(g_configManager.GetHttpTimeout(), g_configManager.GetReadTimeout());
    g_httpClient.SetMaxRetries(g_configManager.GetMaxRetries());

    // Sync current state for modules that use EAState* pointer
    SyncCurrentState();

    // MarketCollector
    g_marketCollector.Init(g_logger, g_httpClient, g_configManager.GetTimeframe());

    // TradeExecutor
    g_tradeExecutor.Init(g_logger, g_httpClient);

    // HealthMonitor
    g_healthMonitor.Init(g_logger, g_httpClient);

    // RecoveryManager
    g_recoveryManager.Init(g_stateMachine, g_httpClient, g_logger);

    // SessionAbortHandler
    g_sessionAbortHandler.Init(g_stateMachine, g_sessionManager, g_tradeExecutor, g_logger);

    // CommandDispatcher
    g_commandDispatcher = new CCommandDispatcher();
    g_commandDispatcher.Init(g_stateMachine, g_sessionManager, g_tradeExecutor, g_logger, g_httpClient);

    //--- Step 5: Transition BOOT → CONNECT
    g_stateMachine.TransitionTo(STATE_CONNECT, "Initialization complete, config valid");
    SyncCurrentState();

    //--- Step 6: Attempt backend connection (heartbeat as connectivity probe)
    g_logger.Info("EAGateway", "Attempting backend connection...");
    g_healthMonitor.SendHeartbeat();

    //--- Step 7: Check connection result
    if(g_httpClient.IsConnected())
    {
        // Connection succeeded → transition CONNECT → WAIT_SESSION
        g_stateMachine.TransitionTo(STATE_WAIT_SESSION, "Backend connected successfully");
        SyncCurrentState();
        g_recoveryManager.OnConnectionSuccess();
        g_logger.Info("EAGateway", "Backend connected. Entering WAIT_SESSION state.");
    }
    else
    {
        // Connection failed → remain in CONNECT (RecoveryManager will handle)
        g_logger.Warn("EAGateway", "Backend connection failed. Staying in CONNECT. Recovery will retry.");
        g_recoveryManager.OnConnectionFailure();
    }

    //--- Step 8: Set timer with 1-second granularity
    EventSetTimer(1);

    // Reset all timer counters
    g_heartbeatCounter      = 0;
    g_sessionCheckCounter   = 0;
    g_orphanCheckCounter    = 0;
    g_positionReportCounter = 0;
    g_signalScanCounter     = 0;

    g_logger.Info("EAGateway", "EA Gateway initialized. Timer set (1s granularity).");

    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert tick function                                                |
//+------------------------------------------------------------------+
void OnTick()
{
    //--- Safety: if modules are not initialized, skip
    if(g_stateMachine == NULL || g_logger == NULL)
        return;

    //--- Sync state for pointer-based modules
    SyncCurrentState();

    //--- 1. MarketCollector.OnTick() (internal state guard)
    if(g_marketCollector != NULL)
        g_marketCollector.OnTick();

    //--- 2. New bar detection
    datetime currentBarTime = iTime(Symbol(), StringToTimeframe(InpTimeframe), 0);
    if(currentBarTime != g_lastBarTime)
    {
        if(g_lastBarTime != 0)  // Skip first call (initialization)
        {
            if(g_marketCollector != NULL)
                g_marketCollector.OnNewBar();
        }
        g_lastBarTime = currentBarTime;
    }

    //--- 3. Session abort check (aborts to WAIT_SESSION if session ended)
    if(g_sessionAbortHandler != NULL)
    {
        g_sessionAbortHandler.CheckSessionAbort();
        SyncCurrentState();
    }

    //--- 4. MT5 connectivity monitoring
    if(g_healthMonitor != NULL)
        g_healthMonitor.MonitorMT5Connectivity();

    //--- 5. State-specific logic
    EAState state = g_stateMachine.GetCurrentState();

    switch(state)
    {
        case STATE_DISCONNECTED:
        {
            // RecoveryManager handles reconnection attempts
            if(g_recoveryManager != NULL)
            {
                OpenPositionInfo posInfo;
                posInfo.hasPosition = false;

                // Check for open position to pass to recovery
                if(g_tradeExecutor != NULL && g_tradeExecutor.HasOpenPosition())
                {
                    posInfo.hasPosition = true;
                    posInfo.ticket      = g_tradeExecutor.GetOpenTicket();

                    if(PositionSelectByTicket((ulong)posInfo.ticket))
                    {
                        long posType = PositionGetInteger(POSITION_TYPE);
                        posInfo.direction = (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL";
                        posInfo.lotSize   = PositionGetDouble(POSITION_VOLUME);
                        posInfo.openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
                    }
                }

                double equity = AccountInfoDouble(ACCOUNT_EQUITY);
                g_recoveryManager.OnDisconnectedTick(posInfo, equity);
                SyncCurrentState();
            }
            break;
        }

        case STATE_CONNECT:
        {
            // If stuck in CONNECT, attempt connection on each tick
            // (but RecoveryManager's disconnection logic will handle escalation)
            break;
        }

        default:
            // Other states: no tick-specific logic beyond market collection
            // (timer handles periodic tasks)
            break;
    }

    //--- Track last stable state for recovery purposes
    if(g_recoveryManager != NULL)
    {
        EAState currentState = g_stateMachine.GetCurrentState();
        g_recoveryManager.SetLastStableState(currentState);
    }
}

//+------------------------------------------------------------------+
//| Timer function - 1 second resolution with internal counters        |
//+------------------------------------------------------------------+
void OnTimer()
{
    //--- Safety: if modules are not initialized, skip
    if(g_stateMachine == NULL || g_logger == NULL)
        return;

    //--- Sync state
    SyncCurrentState();

    //--- Increment all counters
    g_heartbeatCounter++;
    g_sessionCheckCounter++;
    g_orphanCheckCounter++;
    g_positionReportCounter++;
    g_signalScanCounter++;

    //--- Get current state for conditional logic
    EAState state = g_stateMachine.GetCurrentState();

    //--- Heartbeat: every InpHeartbeatSec seconds
    if(g_heartbeatCounter >= InpHeartbeatSec)
    {
        g_heartbeatCounter = 0;

        if(g_healthMonitor != NULL)
        {
            g_healthMonitor.SendHeartbeat();

            // Track connection success/failure for RecoveryManager
            if(g_recoveryManager != NULL)
            {
                if(g_httpClient != NULL && g_httpClient.IsConnected())
                    g_recoveryManager.OnConnectionSuccess();
                else
                    g_recoveryManager.OnConnectionFailure();
            }

            // Check if disconnection threshold reached
            if(g_recoveryManager != NULL && g_recoveryManager.ShouldEnterDisconnected())
            {
                if(state != STATE_DISCONNECTED)
                {
                    g_stateMachine.TransitionTo(STATE_DISCONNECTED, "10 consecutive connection failures");
                    SyncCurrentState();
                }
            }
        }
    }

    //--- Session check: every 60s (only in WAIT_SESSION)
    if(g_sessionCheckCounter >= SESSION_CHECK_INTERVAL_SEC)
    {
        g_sessionCheckCounter = 0;

        if(state == STATE_WAIT_SESSION)
        {
            if(g_sessionManager != NULL && g_sessionManager.IsInSession())
            {
                // Session is active - attempt transition to CHECK_RISK
                bool transitioned = g_stateMachine.TransitionTo(STATE_CHECK_RISK, "session_active");
                if(transitioned)
                {
                    SyncCurrentState();
                    g_logger.Info("EAGateway", "Session active. Transitioned to CHECK_RISK.");
                }
            }
        }
    }

    //--- Signal scan: every SIGNAL_SCAN_INTERVAL_SEC (for CHECK_RISK, SCAN_SIGNAL, AI_CONFIRMATION)
    if(g_signalScanCounter >= SIGNAL_SCAN_INTERVAL_SEC)
    {
        g_signalScanCounter = 0;

        //--- CHECK_RISK → SCAN_SIGNAL: request backend to check risk and scan for signal
        if(state == STATE_CHECK_RISK)
        {
            bool approved = RequestBackendTransition(STATE_CHECK_RISK, STATE_SCAN_SIGNAL, "risk_check_and_scan");
            if(approved)
            {
                g_logger.Info("EAGateway", "Risk check passed. Transitioned to SCAN_SIGNAL.");
            }
            else
            {
                g_logger.Info("EAGateway", "Risk check rejected or session ended. Going back to WAIT_SESSION.");
                g_stateMachine.TransitionTo(STATE_WAIT_SESSION, "risk_check_rejected");
                SyncCurrentState();
            }
        }

        //--- SCAN_SIGNAL → AI_CONFIRMATION: backend runs signal engine
        else if(state == STATE_SCAN_SIGNAL)
        {
            bool approved = RequestBackendTransition(STATE_SCAN_SIGNAL, STATE_AI_CONFIRMATION, "signal_scan");
            if(approved)
            {
                g_logger.Info("EAGateway", "Signal detected! Transitioned to AI_CONFIRMATION.");
            }
            else
            {
                // No signal detected → go back to WAIT_SESSION
                g_stateMachine.TransitionTo(STATE_WAIT_SESSION, "no_signal_detected");
                SyncCurrentState();
                g_logger.Info("EAGateway", "No signal detected. Back to WAIT_SESSION.");
            }
        }

        //--- AI_CONFIRMATION → OPEN_POSITION: backend approves trade + sends command
        else if(state == STATE_AI_CONFIRMATION)
        {
            bool approved = RequestBackendTransition(STATE_AI_CONFIRMATION, STATE_OPEN_POSITION, "ai_approved");
            if(approved)
            {
                g_logger.Info("EAGateway", "Trade approved! Transitioned to OPEN_POSITION.");
                // CommandDispatcher already dispatched the trade command from the response
            }
            else
            {
                g_stateMachine.TransitionTo(STATE_WAIT_SESSION, "ai_rejected_trade");
                SyncCurrentState();
                g_logger.Info("EAGateway", "Trade rejected by AI. Back to WAIT_SESSION.");
            }
        }

        //--- OPEN_POSITION → MANAGE_POSITION: check trade result from backend
        else if(state == STATE_OPEN_POSITION)
        {
            bool approved = RequestBackendTransition(STATE_OPEN_POSITION, STATE_MANAGE_POSITION, "trade_confirmed");
            if(approved)
            {
                g_logger.Info("EAGateway", "Trade confirmed. Transitioned to MANAGE_POSITION.");
            }
            else
            {
                g_logger.Info("EAGateway", "Trade result not yet confirmed. Waiting...");
            }
        }

        //--- MANAGE_POSITION → POSITION_CLOSED: check if position is still open
        else if(state == STATE_MANAGE_POSITION)
        {
            if(g_tradeExecutor != NULL && !g_tradeExecutor.HasOpenPosition())
            {
                // Position closed (SL/TP hit or manual close)
                g_stateMachine.TransitionTo(STATE_POSITION_CLOSED, "position_closed");
                SyncCurrentState();
                g_logger.Info("EAGateway", "Position closed. Transitioned to POSITION_CLOSED.");

                // Then go back to WAIT_SESSION
                g_stateMachine.TransitionTo(STATE_WAIT_SESSION, "ready_for_next_session");
                SyncCurrentState();
                g_logger.Info("EAGateway", "Back to WAIT_SESSION. Ready for next signal.");
            }
        }
    }

    //--- Orphan position detection: every 60s
    if(g_orphanCheckCounter >= ORPHAN_CHECK_INTERVAL_SEC)
    {
        g_orphanCheckCounter = 0;

        if(g_healthMonitor != NULL && state != STATE_BOOT && state != STATE_CONNECT)
        {
            g_healthMonitor.CheckOrphanPositions();
        }
    }

    //--- Position status reporting: every 5s (only in MANAGE_POSITION)
    if(g_positionReportCounter >= POSITION_REPORT_SEC)
    {
        g_positionReportCounter = 0;

        if(state == STATE_MANAGE_POSITION)
        {
            if(g_httpClient != NULL && g_tradeExecutor != NULL && g_tradeExecutor.HasOpenPosition())
            {
                string statusJson = BuildPositionStatusJson();
                if(StringLen(statusJson) > 0)
                {
                    HttpResponse response = g_httpClient.Post(POSITION_STATUS_ENDPOINT, statusJson);
                    if(response.statusCode < 200 || response.statusCode >= 300)
                    {
                        g_logger.Warn("EAGateway", "Position status report failed. Status: " +
                                     IntegerToString(response.statusCode));
                    }
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                    |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    //--- Step 1: Log shutdown reason
    if(g_logger != NULL)
    {
        string reasonStr = "";
        switch(reason)
        {
            case REASON_PROGRAM:     reasonStr = "PROGRAM (EA removed)";       break;
            case REASON_REMOVE:      reasonStr = "REMOVE (EA removed from chart)"; break;
            case REASON_RECOMPILE:   reasonStr = "RECOMPILE (EA recompiled)";  break;
            case REASON_CHARTCHANGE: reasonStr = "CHARTCHANGE (symbol/period changed)"; break;
            case REASON_CHARTCLOSE:  reasonStr = "CHARTCLOSE (chart closed)";  break;
            case REASON_PARAMETERS:  reasonStr = "PARAMETERS (inputs changed)"; break;
            case REASON_ACCOUNT:     reasonStr = "ACCOUNT (account changed)";  break;
            case REASON_TEMPLATE:    reasonStr = "TEMPLATE (template applied)"; break;
            case REASON_INITFAILED:  reasonStr = "INITFAILED (init failed)";   break;
            case REASON_CLOSE:       reasonStr = "CLOSE (terminal closed)";    break;
            default:                 reasonStr = "UNKNOWN (" + IntegerToString(reason) + ")"; break;
        }
        g_logger.Info("EAGateway", "EA Gateway shutting down. Reason: " + reasonStr);
    }

    //--- Step 2: Delete all module pointers (order: dependents first)
    if(g_sessionAbortHandler != NULL) { delete g_sessionAbortHandler; g_sessionAbortHandler = NULL; }
    if(g_commandDispatcher != NULL)   { delete g_commandDispatcher;   g_commandDispatcher = NULL; }
    if(g_recoveryManager != NULL)     { delete g_recoveryManager;     g_recoveryManager = NULL; }
    if(g_healthMonitor != NULL)       { delete g_healthMonitor;       g_healthMonitor = NULL; }
    if(g_tradeExecutor != NULL)       { delete g_tradeExecutor;       g_tradeExecutor = NULL; }
    if(g_marketCollector != NULL)     { delete g_marketCollector;     g_marketCollector = NULL; }
    if(g_sessionManager != NULL)      { delete g_sessionManager;      g_sessionManager = NULL; }
    if(g_httpClient != NULL)          { delete g_httpClient;          g_httpClient = NULL; }
    if(g_stateMachine != NULL)        { delete g_stateMachine;        g_stateMachine = NULL; }
    if(g_logger != NULL)              { delete g_logger;              g_logger = NULL; }
    if(g_configManager != NULL)       { delete g_configManager;       g_configManager = NULL; }

    //--- Step 3: Kill timer
    EventKillTimer();
}
//+------------------------------------------------------------------+
