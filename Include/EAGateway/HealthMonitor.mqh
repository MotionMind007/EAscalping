//+------------------------------------------------------------------+
//|                                                HealthMonitor.mqh   |
//|                         EA Gateway - Health Monitoring              |
//|                         Heartbeat, connectivity, orphan detection   |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_HEALTHMONITOR_MQH
#define EA_GATEWAY_HEALTHMONITOR_MQH

#include "Types.mqh"
#include "Logger.mqh"
#include "HttpClient.mqh"

//+------------------------------------------------------------------+
//| Constants                                                          |
//+------------------------------------------------------------------+
#define HEALTH_HEARTBEAT_ENDPOINT     "/api/v1/health/heartbeat"
#define HEALTH_ORPHAN_ENDPOINT        "/api/v1/position/orphan"
#define HEALTH_KNOWN_POS_ENDPOINT     "/api/v1/position/known"
#define HEALTH_DISCONNECT_ENDPOINT    "/api/v1/health/mt5disconnect"
#define HEALTH_RECONNECT_ENDPOINT     "/api/v1/health/mt5reconnect"
#define HEALTH_MT5_POLL_INTERVAL_MS   1000   // Poll MT5 connectivity every 1 second

//+------------------------------------------------------------------+
//| CHealthMonitor - Heartbeat, MT5 connectivity, orphan detection     |
//+------------------------------------------------------------------+
class CHealthMonitor
{
private:
    CLogger*      m_logger;              // Pointer to logger instance
    CHttpClient*  m_httpClient;          // Pointer to HTTP client
    EAState*      m_statePtr;            // Pointer to current EA state

    //--- Heartbeat state
    datetime      m_lastHeartbeatTime;   // Timestamp of last successful heartbeat

    //--- MT5 connectivity tracking
    bool          m_previousMT5Status;   // Previous MT5 connection status
    bool          m_tradeExecutionPaused; // Whether trade execution is paused

    //--- Orphan detection state
    datetime      m_lastOrphanCheckTime; // Timestamp of last orphan check

    //--- Private helpers
    string        FormatTimestamp(datetime time);
    string        StateToString(EAState state);
    void          OnMT5Disconnect();
    void          OnMT5Reconnect();
    string        SerializeHeartbeat();
    string        SerializeOrphanPosition(long ticket, string symbol, string direction,
                                          double lotSize, double openPrice, datetime openTime);

public:
    //--- Constructor / Destructor
                  CHealthMonitor();
                 ~CHealthMonitor();

    //--- Initialization
    void          Init(CLogger* logger, CHttpClient* httpClient, EAState* statePtr);

    //--- Core health monitoring
    void          SendHeartbeat();            // Called by timer (every 30s)
    string        GetHealthStatus();          // For polling endpoint response
    bool          IsMT5Connected();           // Check MT5 trade server connection
    void          CheckOrphanPositions();     // Every 60s

    //--- MT5 connectivity monitoring (call frequently, e.g., on tick or timer)
    void          MonitorMT5Connectivity();

    //--- Accessors
    bool          IsTradeExecutionPaused();
    datetime      GetLastHeartbeatTime();
};

//+------------------------------------------------------------------+
//| Constructor                                                        |
//+------------------------------------------------------------------+
CHealthMonitor::CHealthMonitor()
{
    m_logger              = NULL;
    m_httpClient          = NULL;
    m_statePtr            = NULL;
    m_lastHeartbeatTime   = 0;
    m_previousMT5Status   = true;   // Assume connected at start
    m_tradeExecutionPaused = false;
    m_lastOrphanCheckTime = 0;
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CHealthMonitor::~CHealthMonitor()
{
    // External references, do not delete
    m_logger     = NULL;
    m_httpClient = NULL;
    m_statePtr   = NULL;
}

//+------------------------------------------------------------------+
//| Init - Configure dependencies                                      |
//+------------------------------------------------------------------+
void CHealthMonitor::Init(CLogger* logger, CHttpClient* httpClient, EAState* statePtr)
{
    m_logger     = logger;
    m_httpClient = httpClient;
    m_statePtr   = statePtr;

    // Initialize MT5 status based on current connectivity
    m_previousMT5Status = IsMT5Connected();

    if(m_logger != NULL)
        m_logger.Info("HealthMonitor", "Health monitor initialized. MT5 connected: " +
                     (m_previousMT5Status ? "true" : "false"));
}

//+------------------------------------------------------------------+
//| IsMT5Connected - Check MT5 trade server connection                 |
//| Uses TerminalInfoInteger(TERMINAL_CONNECTED) to detect status      |
//+------------------------------------------------------------------+
bool CHealthMonitor::IsMT5Connected()
{
    return (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
}

//+------------------------------------------------------------------+
//| MonitorMT5Connectivity - Detect connect/disconnect transitions      |
//| Should be called frequently (on tick or every 1s via timer)        |
//+------------------------------------------------------------------+
void CHealthMonitor::MonitorMT5Connectivity()
{
    bool currentStatus = IsMT5Connected();

    // Detect transition: connected → disconnected
    if(m_previousMT5Status && !currentStatus)
    {
        OnMT5Disconnect();
    }
    // Detect transition: disconnected → connected
    else if(!m_previousMT5Status && currentStatus)
    {
        OnMT5Reconnect();
    }

    m_previousMT5Status = currentStatus;
}

//+------------------------------------------------------------------+
//| OnMT5Disconnect - Handle MT5 trade server disconnection            |
//| Requirements 5.4: Report within 1 second, pause trade execution    |
//+------------------------------------------------------------------+
void CHealthMonitor::OnMT5Disconnect()
{
    m_tradeExecutionPaused = true;

    if(m_logger != NULL)
        m_logger.Error("HealthMonitor", "MT5 trade server disconnected. Trade execution paused.");

    // Report disconnection to backend within 1 second
    if(m_httpClient != NULL)
    {
        string currentState = "";
        if(m_statePtr != NULL)
            currentState = StateToString(*m_statePtr);

        string json = "{";
        json += "\"event\":\"mt5_disconnected\",";
        json += "\"state\":\"" + currentState + "\",";
        json += "\"timestamp\":\"" + FormatTimestamp(TimeGMT()) + "\"";
        json += "}";

        HttpResponse response = m_httpClient.Post(HEALTH_DISCONNECT_ENDPOINT, json);

        if(response.statusCode >= 200 && response.statusCode < 300)
        {
            if(m_logger != NULL)
                m_logger.Info("HealthMonitor", "MT5 disconnection reported to backend successfully");
        }
        else
        {
            if(m_logger != NULL)
                m_logger.Warn("HealthMonitor", "Failed to report MT5 disconnection to backend. Status: " +
                             IntegerToString(response.statusCode));
        }
    }
}

//+------------------------------------------------------------------+
//| OnMT5Reconnect - Handle MT5 trade server reconnection              |
//| Requirements 5.5: Resume execution, report, sync state             |
//+------------------------------------------------------------------+
void CHealthMonitor::OnMT5Reconnect()
{
    m_tradeExecutionPaused = false;

    if(m_logger != NULL)
        m_logger.Info("HealthMonitor", "MT5 trade server reconnected. Resuming trade execution.");

    // Report reconnection to backend and sync state
    if(m_httpClient != NULL)
    {
        string currentState = "";
        if(m_statePtr != NULL)
            currentState = StateToString(*m_statePtr);

        // Build reconnection payload with current state for sync
        string json = "{";
        json += "\"event\":\"mt5_reconnected\",";
        json += "\"state\":\"" + currentState + "\",";
        json += "\"account_balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
        json += "\"account_equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
        json += "\"timestamp\":\"" + FormatTimestamp(TimeGMT()) + "\"";
        json += "}";

        HttpResponse response = m_httpClient.Post(HEALTH_RECONNECT_ENDPOINT, json);

        if(response.statusCode >= 200 && response.statusCode < 300)
        {
            if(m_logger != NULL)
                m_logger.Info("HealthMonitor", "MT5 reconnection reported and state synced with backend");
        }
        else
        {
            if(m_logger != NULL)
                m_logger.Warn("HealthMonitor", "Failed to report MT5 reconnection to backend. Status: " +
                             IntegerToString(response.statusCode));
        }
    }
}

//+------------------------------------------------------------------+
//| SendHeartbeat - Serialize and send heartbeat payload to backend     |
//| Called every 30 seconds (±2s tolerance)                            |
//| POST /api/v1/health/heartbeat                                      |
//+------------------------------------------------------------------+
void CHealthMonitor::SendHeartbeat()
{
    if(m_httpClient == NULL)
    {
        if(m_logger != NULL)
            m_logger.Error("HealthMonitor", "Cannot send heartbeat: HttpClient is NULL");
        return;
    }

    string json = SerializeHeartbeat();

    HttpResponse response = m_httpClient.Post(HEALTH_HEARTBEAT_ENDPOINT, json);

    if(response.statusCode >= 200 && response.statusCode < 300)
    {
        m_lastHeartbeatTime = TimeGMT();

        if(m_logger != NULL)
            m_logger.Info("HealthMonitor", "Heartbeat sent successfully. Latency: " +
                         IntegerToString(response.latencyMs) + "ms");
    }
    else
    {
        if(m_logger != NULL)
            m_logger.Warn("HealthMonitor", "Heartbeat failed. Status: " +
                         IntegerToString(response.statusCode));
    }
}

//+------------------------------------------------------------------+
//| SerializeHeartbeat - Build heartbeat JSON payload                   |
//| Fields: state, account_balance, account_equity, latency_ms,        |
//|         mt5_connected, spread, timestamp                           |
//+------------------------------------------------------------------+
string CHealthMonitor::SerializeHeartbeat()
{
    string currentState = "";
    if(m_statePtr != NULL)
        currentState = StateToString(*m_statePtr);

    double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
    int    latency  = (m_httpClient != NULL) ? m_httpClient.GetLastLatencyMs() : 0;
    bool   mt5Conn  = IsMT5Connected();
    int    spread   = (int)SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);

    string json = "{";
    json += "\"state\":\"" + currentState + "\",";
    json += "\"account_balance\":" + DoubleToString(balance, 2) + ",";
    json += "\"account_equity\":" + DoubleToString(equity, 2) + ",";
    json += "\"latency_ms\":" + IntegerToString(latency) + ",";
    json += "\"mt5_connected\":" + (mt5Conn ? "true" : "false") + ",";
    json += "\"spread\":" + IntegerToString(spread) + ",";
    json += "\"timestamp\":\"" + FormatTimestamp(TimeGMT()) + "\"";
    json += "}";

    return json;
}

//+------------------------------------------------------------------+
//| GetHealthStatus - Return JSON health payload for polling endpoint   |
//| Requirements 5.3: Respond within 1 second with full health data    |
//+------------------------------------------------------------------+
string CHealthMonitor::GetHealthStatus()
{
    string currentState = "";
    if(m_statePtr != NULL)
        currentState = StateToString(*m_statePtr);

    double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
    int    latency  = (m_httpClient != NULL) ? m_httpClient.GetLastLatencyMs() : 0;
    bool   mt5Conn  = IsMT5Connected();
    int    spread   = (int)SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);

    string json = "{";
    json += "\"state\":\"" + currentState + "\",";
    json += "\"account_balance\":" + DoubleToString(balance, 2) + ",";
    json += "\"account_equity\":" + DoubleToString(equity, 2) + ",";
    json += "\"latency_ms\":" + IntegerToString(latency) + ",";
    json += "\"mt5_connected\":" + (mt5Conn ? "true" : "false") + ",";
    json += "\"spread\":" + IntegerToString(spread) + ",";
    json += "\"last_heartbeat_utc\":\"" + FormatTimestamp(m_lastHeartbeatTime) + "\"";
    json += "}";

    return json;
}

//+------------------------------------------------------------------+
//| CheckOrphanPositions - Query backend for known positions, compare  |
//| against MT5 open positions, report orphans                         |
//| Requirements 7.4, 7.6: Every 60 seconds                           |
//+------------------------------------------------------------------+
void CHealthMonitor::CheckOrphanPositions()
{
    if(m_httpClient == NULL)
    {
        if(m_logger != NULL)
            m_logger.Error("HealthMonitor", "Cannot check orphan positions: HttpClient is NULL");
        return;
    }

    //--- Query backend for known open positions
    string requestJson = "{\"symbol\":\"" + Symbol() + "\"}";
    HttpResponse response = m_httpClient.Post(HEALTH_KNOWN_POS_ENDPOINT, requestJson);

    if(response.statusCode < 200 || response.statusCode >= 300 || !response.isValid)
    {
        if(m_logger != NULL)
            m_logger.Warn("HealthMonitor", "Failed to query known positions from backend. Status: " +
                         IntegerToString(response.statusCode));
        return;
    }

    //--- Parse backend-known ticket numbers from response body
    //    Expected response format: {"tickets":[123456789, 987654321]}
    //    We extract ticket numbers using simple string parsing
    long backendTickets[];
    int backendTicketCount = 0;

    // Find the "tickets" array in the response
    int ticketsStart = StringFind(response.body, "\"tickets\"");
    if(ticketsStart >= 0)
    {
        int arrayStart = StringFind(response.body, "[", ticketsStart);
        int arrayEnd   = StringFind(response.body, "]", arrayStart);

        if(arrayStart >= 0 && arrayEnd > arrayStart)
        {
            string arrayContent = StringSubstr(response.body, arrayStart + 1, arrayEnd - arrayStart - 1);

            // Parse comma-separated ticket numbers
            string tickets[];
            int count = StringSplit(arrayContent, ',', tickets);

            ArrayResize(backendTickets, count);
            for(int i = 0; i < count; i++)
            {
                StringTrimLeft(tickets[i]);
                StringTrimRight(tickets[i]);
                if(StringLen(tickets[i]) > 0)
                {
                    backendTickets[backendTicketCount] = StringToInteger(tickets[i]);
                    backendTicketCount++;
                }
            }
            ArrayResize(backendTickets, backendTicketCount);
        }
    }

    //--- Compare MT5 open positions against backend-known positions
    int totalPositions = PositionsTotal();
    int orphansFound = 0;

    for(int i = 0; i < totalPositions; i++)
    {
        long ticket = (long)PositionGetTicket(i);
        if(ticket <= 0)
            continue;

        // Check if this ticket is known to the backend
        bool isKnown = false;
        for(int j = 0; j < backendTicketCount; j++)
        {
            if(backendTickets[j] == ticket)
            {
                isKnown = true;
                break;
            }
        }

        // If not known to backend, it's an orphan — report it
        if(!isKnown)
        {
            // Select the position to get details
            if(PositionSelectByTicket(ticket))
            {
                string symbol    = PositionGetString(POSITION_SYMBOL);
                long   posType   = PositionGetInteger(POSITION_TYPE);
                string direction = (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL";
                double lotSize   = PositionGetDouble(POSITION_VOLUME);
                double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
                datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);

                string orphanJson = SerializeOrphanPosition(ticket, symbol, direction,
                                                            lotSize, openPrice, openTime);

                HttpResponse orphanResponse = m_httpClient.Post(HEALTH_ORPHAN_ENDPOINT, orphanJson);

                if(orphanResponse.statusCode >= 200 && orphanResponse.statusCode < 300)
                {
                    orphansFound++;
                    if(m_logger != NULL)
                        m_logger.Warn("HealthMonitor", "Orphan position reported: Ticket=" +
                                     IntegerToString(ticket) + " Symbol=" + symbol +
                                     " Direction=" + direction + " Lots=" + DoubleToString(lotSize, 2));
                }
                else
                {
                    if(m_logger != NULL)
                        m_logger.Error("HealthMonitor", "Failed to report orphan position. Ticket=" +
                                      IntegerToString(ticket) + " Status: " +
                                      IntegerToString(orphanResponse.statusCode));
                }
            }
        }
    }

    m_lastOrphanCheckTime = TimeGMT();

    if(m_logger != NULL && orphansFound > 0)
        m_logger.Info("HealthMonitor", "Orphan check complete. Orphans reported: " +
                     IntegerToString(orphansFound));
}

//+------------------------------------------------------------------+
//| SerializeOrphanPosition - Build orphan position JSON payload       |
//| POST /api/v1/position/orphan                                       |
//+------------------------------------------------------------------+
string CHealthMonitor::SerializeOrphanPosition(long ticket, string symbol, string direction,
                                                double lotSize, double openPrice, datetime openTime)
{
    string json = "{";
    json += "\"ticket\":" + IntegerToString(ticket) + ",";
    json += "\"symbol\":\"" + symbol + "\",";
    json += "\"direction\":\"" + direction + "\",";
    json += "\"lot_size\":" + DoubleToString(lotSize, 2) + ",";
    json += "\"open_price\":" + DoubleToString(openPrice, 2) + ",";
    json += "\"open_time\":\"" + FormatTimestamp(openTime) + "\"";
    json += "}";

    return json;
}

//+------------------------------------------------------------------+
//| FormatTimestamp - Format datetime as ISO 8601 UTC with ms          |
//| Format: yyyy-MM-ddTHH:mm:ss.fffZ                                  |
//+------------------------------------------------------------------+
string CHealthMonitor::FormatTimestamp(datetime time)
{
    MqlDateTime dt;
    TimeToStruct(time, dt);

    // Best effort milliseconds from GetTickCount
    int milliseconds = (int)(GetTickCount() % 1000);

    string timestamp = StringFormat("%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
                                   dt.year, dt.mon, dt.day,
                                   dt.hour, dt.min, dt.sec,
                                   milliseconds);
    return timestamp;
}

//+------------------------------------------------------------------+
//| StateToString - Convert EAState enum to string for payloads        |
//+------------------------------------------------------------------+
string CHealthMonitor::StateToString(EAState state)
{
    switch(state)
    {
        case STATE_BOOT:              return "BOOT";
        case STATE_CONNECT:           return "CONNECT";
        case STATE_WAIT_SESSION:      return "WAIT_SESSION";
        case STATE_CHECK_RISK:        return "CHECK_RISK";
        case STATE_SCAN_SIGNAL:       return "SCAN_SIGNAL";
        case STATE_AI_CONFIRMATION:   return "AI_CONFIRMATION";
        case STATE_OPEN_POSITION:     return "OPEN_POSITION";
        case STATE_MANAGE_POSITION:   return "MANAGE_POSITION";
        case STATE_POSITION_CLOSED:   return "POSITION_CLOSED";
        case STATE_DISCONNECTED:      return "DISCONNECTED";
        default:                      return "UNKNOWN";
    }
}

//+------------------------------------------------------------------+
//| IsTradeExecutionPaused - Check if trade execution is paused        |
//| Returns true when MT5 is disconnected from trade server            |
//+------------------------------------------------------------------+
bool CHealthMonitor::IsTradeExecutionPaused()
{
    return m_tradeExecutionPaused;
}

//+------------------------------------------------------------------+
//| GetLastHeartbeatTime - Return timestamp of last successful heartbeat|
//+------------------------------------------------------------------+
datetime CHealthMonitor::GetLastHeartbeatTime()
{
    return m_lastHeartbeatTime;
}

#endif // EA_GATEWAY_HEALTHMONITOR_MQH
