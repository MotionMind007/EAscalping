//+------------------------------------------------------------------+
//|                                              RecoveryManager.mqh   |
//|                         EA Gateway - Disconnection & Recovery       |
//|                         Handles reconnection, state recovery,       |
//|                         orphan detection, and exception handling    |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_RECOVERYMANAGER_MQH
#define EA_GATEWAY_RECOVERYMANAGER_MQH

#include "Types.mqh"
#include "Logger.mqh"
#include "StateMachine.mqh"
#include "HttpClient.mqh"

//+------------------------------------------------------------------+
//| Constants                                                          |
//+------------------------------------------------------------------+
#define RECOVERY_DISCONNECT_THRESHOLD   10     // Consecutive failures to enter DISCONNECTED
#define RECOVERY_RETRY_INTERVAL_SEC     60     // Retry interval in DISCONNECTED state (seconds)
#define RECOVERY_CONFIRMATION_TIMEOUT   10000  // Backend state confirmation timeout (ms)
#define RECOVERY_EXCEPTION_NOTIFY_MS    5000   // Max time to notify backend of exception (ms)
#define RECOVERY_ENDPOINT              "/api/v1/state/recovery"

//+------------------------------------------------------------------+
//| OpenPositionInfo - Struct holding open position details for recovery|
//+------------------------------------------------------------------+
struct OpenPositionInfo
{
    long     ticket;           // Position ticket number
    string   direction;        // "BUY" or "SELL"
    double   lotSize;          // Lot size
    double   openPrice;        // Entry price
    bool     hasPosition;      // Whether a position is currently open
};

//+------------------------------------------------------------------+
//| CRecoveryManager - Disconnection, recovery, and exception handler  |
//+------------------------------------------------------------------+
class CRecoveryManager
{
private:
    CStateMachine*   m_stateMachine;          // Pointer to state machine
    CHttpClient*     m_httpClient;            // Pointer to HTTP client
    CLogger*         m_logger;                // Pointer to logger

    int              m_consecutiveFailures;   // Consecutive connection failure count
    EAState          m_lastStableState;       // Last known stable state before error
    datetime         m_lastRetryTime;         // Last reconnection retry timestamp
    bool             m_isInRecovery;          // Whether currently in recovery process

    //--- Private helpers
    string           FormatTimestamp();
    string           BuildRecoveryPayload(OpenPositionInfo &posInfo, double accountEquity);
    string           BuildExceptionPayload(string exceptionInfo, EAState recoveredState);
    bool             ParseStateConfirmation(const string &responseBody, EAState &confirmedState);

public:
    //--- Constructor / Destructor
                     CRecoveryManager();
                    ~CRecoveryManager();

    //--- Initialization
    void             Init(CStateMachine* stateMachine, CHttpClient* httpClient, CLogger* logger);

    //--- Disconnection protocol (Req 7.2)
    void             OnConnectionFailure();
    void             OnConnectionSuccess();
    bool             ShouldEnterDisconnected();
    bool             IsDisconnected();
    void             OnDisconnectedTick(OpenPositionInfo &posInfo, double accountEquity);

    //--- Recovery protocol (Req 7.3)
    bool             AttemptRecovery(OpenPositionInfo &posInfo, double accountEquity);

    //--- Unhandled exception recovery (Req 7.1)
    void             HandleException(string exceptionInfo);

    //--- Orphan position reporting (Req 7.4)
    bool             ReportOrphanPosition(long ticket, string symbol, string direction,
                                          double lotSize, double openPrice, datetime openTime);

    //--- Accessors
    int              GetConsecutiveFailures() const;
    EAState          GetLastStableState() const;
    void             SetLastStableState(EAState state);
    bool             IsInRecovery() const;
};

//+------------------------------------------------------------------+
//| Constructor                                                        |
//+------------------------------------------------------------------+
CRecoveryManager::CRecoveryManager()
{
    m_stateMachine       = NULL;
    m_httpClient         = NULL;
    m_logger             = NULL;
    m_consecutiveFailures = 0;
    m_lastStableState    = STATE_WAIT_SESSION;
    m_lastRetryTime      = 0;
    m_isInRecovery       = false;
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CRecoveryManager::~CRecoveryManager()
{
    // Pointers are externally owned, do not delete
    m_stateMachine = NULL;
    m_httpClient   = NULL;
    m_logger       = NULL;
}

//+------------------------------------------------------------------+
//| Init - Set dependencies                                            |
//+------------------------------------------------------------------+
void CRecoveryManager::Init(CStateMachine* stateMachine, CHttpClient* httpClient, CLogger* logger)
{
    m_stateMachine = stateMachine;
    m_httpClient   = httpClient;
    m_logger       = logger;

    if(m_logger != NULL)
        m_logger.Info("RecoveryManager", "RecoveryManager initialized");
}

//+------------------------------------------------------------------+
//| FormatTimestamp - Generate ISO 8601 UTC timestamp with milliseconds |
//| Format: yyyy-MM-ddTHH:mm:ss.fffZ                                  |
//+------------------------------------------------------------------+
string CRecoveryManager::FormatTimestamp()
{
    datetime now = TimeGMT();
    MqlDateTime dt;
    TimeToStruct(now, dt);

    int milliseconds = (int)(GetTickCount() % 1000);

    string timestamp = StringFormat("%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
                                   dt.year, dt.mon, dt.day,
                                   dt.hour, dt.min, dt.sec,
                                   milliseconds);
    return timestamp;
}

//+------------------------------------------------------------------+
//| OnConnectionFailure - Increment consecutive failure counter        |
//| Called when an HTTP request to the backend fails                    |
//+------------------------------------------------------------------+
void CRecoveryManager::OnConnectionFailure()
{
    m_consecutiveFailures++;

    if(m_logger != NULL)
        m_logger.Warn("RecoveryManager", "Connection failure #" +
                     IntegerToString(m_consecutiveFailures) + "/" +
                     IntegerToString(RECOVERY_DISCONNECT_THRESHOLD));
}

//+------------------------------------------------------------------+
//| OnConnectionSuccess - Reset consecutive failure counter            |
//| Called when an HTTP request to the backend succeeds                 |
//+------------------------------------------------------------------+
void CRecoveryManager::OnConnectionSuccess()
{
    if(m_consecutiveFailures > 0)
    {
        if(m_logger != NULL)
            m_logger.Info("RecoveryManager", "Connection restored after " +
                         IntegerToString(m_consecutiveFailures) + " failures");
    }
    m_consecutiveFailures = 0;
}

//+------------------------------------------------------------------+
//| ShouldEnterDisconnected - Check if failure threshold reached        |
//| Returns true when 10 consecutive failures have occurred            |
//+------------------------------------------------------------------+
bool CRecoveryManager::ShouldEnterDisconnected()
{
    return (m_consecutiveFailures >= RECOVERY_DISCONNECT_THRESHOLD);
}

//+------------------------------------------------------------------+
//| IsDisconnected - Check if currently in DISCONNECTED state           |
//+------------------------------------------------------------------+
bool CRecoveryManager::IsDisconnected()
{
    if(m_stateMachine == NULL)
        return false;

    return (m_stateMachine.GetCurrentState() == STATE_DISCONNECTED);
}

//+------------------------------------------------------------------+
//| OnDisconnectedTick - Called every tick while in DISCONNECTED state  |
//|                                                                    |
//| Behavior:                                                          |
//| - Trade execution is halted (no new trades)                        |
//| - SL/TP remain active on MT5 server side                           |
//| - Retry connection every 60 seconds                                |
//| - On successful backend response: initiate recovery                |
//+------------------------------------------------------------------+
void CRecoveryManager::OnDisconnectedTick(OpenPositionInfo &posInfo, double accountEquity)
{
    if(m_stateMachine == NULL || m_httpClient == NULL)
        return;

    // Only retry every RECOVERY_RETRY_INTERVAL_SEC seconds
    datetime currentTime = TimeGMT();
    if(currentTime - m_lastRetryTime < RECOVERY_RETRY_INTERVAL_SEC)
        return;

    m_lastRetryTime = currentTime;

    if(m_logger != NULL)
        m_logger.Info("RecoveryManager", "Attempting reconnection (DISCONNECTED state)...");

    // Attempt recovery by sending current state to backend
    bool recovered = AttemptRecovery(posInfo, accountEquity);

    if(recovered)
    {
        if(m_logger != NULL)
            m_logger.Info("RecoveryManager", "Recovery successful. Resuming operation.");
    }
    else
    {
        if(m_logger != NULL)
            m_logger.Warn("RecoveryManager", "Reconnection attempt failed. Will retry in " +
                         IntegerToString(RECOVERY_RETRY_INTERVAL_SEC) + " seconds.");
    }
}

//+------------------------------------------------------------------+
//| AttemptRecovery - Send recovery payload and await state confirmation|
//|                                                                    |
//| Recovery protocol (Req 7.3):                                       |
//| 1. Send current state, open position details, account equity       |
//| 2. Wait for backend state confirmation within 10 seconds           |
//| 3. On confirmation: transition to backend-confirmed state          |
//| 4. On timeout/failure: remain DISCONNECTED, retry later            |
//|                                                                    |
//| Returns true if recovery succeeded, false otherwise                |
//+------------------------------------------------------------------+
bool CRecoveryManager::AttemptRecovery(OpenPositionInfo &posInfo, double accountEquity)
{
    if(m_httpClient == NULL || m_stateMachine == NULL)
        return false;

    m_isInRecovery = true;

    //--- Build recovery payload
    string payload = BuildRecoveryPayload(posInfo, accountEquity);

    if(m_logger != NULL)
        m_logger.Info("RecoveryManager", "Sending recovery payload to " + RECOVERY_ENDPOINT);

    //--- Send recovery request (includes built-in timeout from HttpClient)
    uint startTime = GetTickCount();
    HttpResponse response = m_httpClient.Post(RECOVERY_ENDPOINT, payload);
    uint elapsed = GetTickCount() - startTime;

    //--- Check if response arrived within confirmation timeout
    if(elapsed > RECOVERY_CONFIRMATION_TIMEOUT)
    {
        if(m_logger != NULL)
            m_logger.Error("RecoveryManager", "Recovery confirmation timed out after " +
                          IntegerToString((int)elapsed) + "ms (limit: " +
                          IntegerToString(RECOVERY_CONFIRMATION_TIMEOUT) + "ms)");
        m_isInRecovery = false;
        return false;
    }

    //--- Check for connection failure
    if(response.statusCode == -1)
    {
        if(m_logger != NULL)
            m_logger.Error("RecoveryManager", "Recovery request failed - backend unreachable");
        m_isInRecovery = false;
        return false;
    }

    //--- Check for successful response with valid JSON
    if(response.statusCode < 200 || response.statusCode >= 300 || !response.isValid)
    {
        if(m_logger != NULL)
            m_logger.Error("RecoveryManager", "Recovery failed - status: " +
                          IntegerToString(response.statusCode) +
                          ", valid JSON: " + (response.isValid ? "yes" : "no"));
        m_isInRecovery = false;
        return false;
    }

    //--- Parse state confirmation from backend response
    EAState confirmedState;
    if(!ParseStateConfirmation(response.body, confirmedState))
    {
        if(m_logger != NULL)
            m_logger.Error("RecoveryManager", "Failed to parse state confirmation from backend response");
        m_isInRecovery = false;
        return false;
    }

    //--- Transition to backend-confirmed state
    bool transitioned = m_stateMachine.TransitionTo(confirmedState,
        "Recovery confirmed by backend");

    if(!transitioned)
    {
        // If normal transition fails, force to WAIT_SESSION as safe fallback
        if(m_logger != NULL)
            m_logger.Warn("RecoveryManager", "Cannot transition to " +
                         m_stateMachine.StateToString(confirmedState) +
                         ". Falling back to WAIT_SESSION.");

        transitioned = m_stateMachine.TransitionTo(STATE_WAIT_SESSION,
            "Recovery fallback to WAIT_SESSION");
    }

    if(transitioned)
    {
        // Reset failure counter on successful recovery
        m_consecutiveFailures = 0;
        m_httpClient.ResetConsecutiveFailures();
        m_lastStableState = m_stateMachine.GetCurrentState();

        if(m_logger != NULL)
            m_logger.Info("RecoveryManager", "State confirmed: " +
                         m_stateMachine.StateToString(m_stateMachine.GetCurrentState()));
    }

    m_isInRecovery = false;
    return transitioned;
}

//+------------------------------------------------------------------+
//| HandleException - Recover from an unhandled exception (Req 7.1)    |
//|                                                                    |
//| Protocol:                                                          |
//| 1. Log exception details                                           |
//| 2. Transition to last stable state (WAIT_SESSION if unknown)       |
//| 3. Notify backend within 5 seconds with exception details          |
//+------------------------------------------------------------------+
void CRecoveryManager::HandleException(string exceptionInfo)
{
    //--- Step 1: Log exception details
    if(m_logger != NULL)
        m_logger.Error("RecoveryManager", "Unhandled exception: " + exceptionInfo);

    //--- Step 2: Determine recovery state
    EAState recoveryState = m_lastStableState;

    // If last stable state is unknown or invalid, default to WAIT_SESSION
    if(recoveryState == STATE_BOOT || recoveryState == STATE_CONNECT ||
       recoveryState == STATE_DISCONNECTED)
    {
        recoveryState = STATE_WAIT_SESSION;
    }

    //--- Step 3: Attempt state transition
    if(m_stateMachine != NULL)
    {
        EAState currentState = m_stateMachine.GetCurrentState();

        // Try to transition to the recovery state
        bool transitioned = m_stateMachine.TransitionTo(recoveryState,
            "Exception recovery: " + exceptionInfo);

        if(!transitioned)
        {
            // If transition to last stable state fails, force WAIT_SESSION
            // via DISCONNECTED as intermediate (ANY → DISCONNECTED → WAIT_SESSION)
            if(m_logger != NULL)
                m_logger.Warn("RecoveryManager", "Direct transition to " +
                             m_stateMachine.StateToString(recoveryState) +
                             " failed. Routing through DISCONNECTED → WAIT_SESSION.");

            m_stateMachine.TransitionTo(STATE_DISCONNECTED, "Exception recovery intermediate");
            m_stateMachine.TransitionTo(STATE_WAIT_SESSION, "Exception recovery final");
        }

        if(m_logger != NULL)
            m_logger.Info("RecoveryManager", "Recovered to state: " +
                         m_stateMachine.StateToString(m_stateMachine.GetCurrentState()));
    }

    //--- Step 4: Notify backend within 5 seconds
    if(m_httpClient != NULL)
    {
        EAState currentRecoveredState = STATE_WAIT_SESSION;
        if(m_stateMachine != NULL)
            currentRecoveredState = m_stateMachine.GetCurrentState();

        string payload = BuildExceptionPayload(exceptionInfo, currentRecoveredState);

        uint startTime = GetTickCount();
        HttpResponse response = m_httpClient.Post(RECOVERY_ENDPOINT, payload);
        uint elapsed = GetTickCount() - startTime;

        if(elapsed > RECOVERY_EXCEPTION_NOTIFY_MS)
        {
            if(m_logger != NULL)
                m_logger.Warn("RecoveryManager", "Exception notification took " +
                             IntegerToString((int)elapsed) + "ms (limit: " +
                             IntegerToString(RECOVERY_EXCEPTION_NOTIFY_MS) + "ms)");
        }

        if(response.statusCode >= 200 && response.statusCode < 300)
        {
            if(m_logger != NULL)
                m_logger.Info("RecoveryManager", "Backend notified of exception recovery");
        }
        else
        {
            if(m_logger != NULL)
                m_logger.Error("RecoveryManager", "Failed to notify backend of exception. Status: " +
                              IntegerToString(response.statusCode));
        }
    }
}

//+------------------------------------------------------------------+
//| ReportOrphanPosition - Report position unknown to backend (Req 7.4)|
//|                                                                    |
//| Sends orphan position details for backend reconciliation           |
//| Endpoint: POST /api/v1/position/orphan                             |
//+------------------------------------------------------------------+
bool CRecoveryManager::ReportOrphanPosition(long ticket, string symbol, string direction,
                                             double lotSize, double openPrice, datetime openTime)
{
    if(m_httpClient == NULL)
        return false;

    //--- Format open_time as ISO 8601
    MqlDateTime dt;
    TimeToStruct(openTime, dt);
    string openTimeStr = StringFormat("%04d-%02d-%02dT%02d:%02d:%02d.000Z",
                                     dt.year, dt.mon, dt.day,
                                     dt.hour, dt.min, dt.sec);

    //--- Build JSON payload
    string payload = "{";
    payload += "\"ticket\":" + IntegerToString(ticket) + ",";
    payload += "\"symbol\":\"" + symbol + "\",";
    payload += "\"direction\":\"" + direction + "\",";
    payload += "\"lot_size\":" + DoubleToString(lotSize, 2) + ",";
    payload += "\"open_price\":" + DoubleToString(openPrice, 2) + ",";
    payload += "\"open_time\":\"" + openTimeStr + "\"";
    payload += "}";

    if(m_logger != NULL)
        m_logger.Info("RecoveryManager", "Reporting orphan position: ticket=" +
                     IntegerToString(ticket) + " " + direction + " " +
                     DoubleToString(lotSize, 2) + " lots @ " + DoubleToString(openPrice, 2));

    HttpResponse response = m_httpClient.Post("/api/v1/position/orphan", payload);

    if(response.statusCode >= 200 && response.statusCode < 300)
    {
        if(m_logger != NULL)
            m_logger.Info("RecoveryManager", "Orphan position reported successfully");
        return true;
    }
    else
    {
        if(m_logger != NULL)
            m_logger.Error("RecoveryManager", "Failed to report orphan position. Status: " +
                          IntegerToString(response.statusCode));
        return false;
    }
}

//+------------------------------------------------------------------+
//| BuildRecoveryPayload - Construct recovery JSON payload             |
//|                                                                    |
//| Format:                                                            |
//| {                                                                  |
//|   "current_state": "MANAGE_POSITION",                              |
//|   "open_position": { "ticket": ..., "direction": ..., ... },       |
//|   "account_equity": 10050.00,                                      |
//|   "timestamp": "2024-01-15T10:30:00.000Z"                          |
//| }                                                                  |
//+------------------------------------------------------------------+
string CRecoveryManager::BuildRecoveryPayload(OpenPositionInfo &posInfo, double accountEquity)
{
    string currentStateStr = "WAIT_SESSION";
    if(m_stateMachine != NULL)
        currentStateStr = m_stateMachine.StateToString(m_stateMachine.GetCurrentState());

    string payload = "{";
    payload += "\"current_state\":\"" + currentStateStr + "\",";

    // Open position (null if no position)
    if(posInfo.hasPosition)
    {
        payload += "\"open_position\":{";
        payload += "\"ticket\":" + IntegerToString(posInfo.ticket) + ",";
        payload += "\"direction\":\"" + posInfo.direction + "\",";
        payload += "\"lot_size\":" + DoubleToString(posInfo.lotSize, 2) + ",";
        payload += "\"open_price\":" + DoubleToString(posInfo.openPrice, 2);
        payload += "},";
    }
    else
    {
        payload += "\"open_position\":null,";
    }

    payload += "\"account_equity\":" + DoubleToString(accountEquity, 2) + ",";
    payload += "\"timestamp\":\"" + FormatTimestamp() + "\"";
    payload += "}";

    return payload;
}

//+------------------------------------------------------------------+
//| BuildExceptionPayload - Construct exception notification payload    |
//|                                                                    |
//| Includes exception details and the state we recovered to           |
//+------------------------------------------------------------------+
string CRecoveryManager::BuildExceptionPayload(string exceptionInfo, EAState recoveredState)
{
    string recoveredStateStr = "WAIT_SESSION";
    if(m_stateMachine != NULL)
        recoveredStateStr = m_stateMachine.StateToString(recoveredState);

    string payload = "{";
    payload += "\"current_state\":\"" + recoveredStateStr + "\",";
    payload += "\"exception\":\"" + exceptionInfo + "\",";
    payload += "\"recovery_type\":\"exception\",";
    payload += "\"open_position\":null,";
    payload += "\"account_equity\":0.0,";
    payload += "\"timestamp\":\"" + FormatTimestamp() + "\"";
    payload += "}";

    return payload;
}

//+------------------------------------------------------------------+
//| ParseStateConfirmation - Extract confirmed state from backend JSON  |
//|                                                                    |
//| Expected response format:                                          |
//| { "confirmed_state": "WAIT_SESSION", ... }                         |
//|                                                                    |
//| Returns true if state was successfully parsed                      |
//+------------------------------------------------------------------+
bool CRecoveryManager::ParseStateConfirmation(const string &responseBody, EAState &confirmedState)
{
    if(m_stateMachine == NULL)
        return false;

    // Search for "confirmed_state" key in JSON
    int keyPos = StringFind(responseBody, "\"confirmed_state\"");
    if(keyPos == -1)
    {
        // Fallback: try "new_state" key (common response format)
        keyPos = StringFind(responseBody, "\"new_state\"");
        if(keyPos == -1)
        {
            // Final fallback: default to WAIT_SESSION if backend responds 2xx
            // but doesn't include explicit state
            confirmedState = STATE_WAIT_SESSION;

            if(m_logger != NULL)
                m_logger.Warn("RecoveryManager", "No state field in recovery response. Defaulting to WAIT_SESSION.");

            return true;
        }
    }

    // Find the colon after the key
    int colonPos = StringFind(responseBody, ":", keyPos);
    if(colonPos == -1)
        return false;

    // Find the opening quote of the value
    int quoteStart = StringFind(responseBody, "\"", colonPos + 1);
    if(quoteStart == -1)
        return false;

    // Find the closing quote of the value
    int quoteEnd = StringFind(responseBody, "\"", quoteStart + 1);
    if(quoteEnd == -1)
        return false;

    // Extract the state string
    string stateStr = StringSubstr(responseBody, quoteStart + 1, quoteEnd - quoteStart - 1);

    // Convert to EAState
    confirmedState = m_stateMachine.StringToState(stateStr);

    if(m_logger != NULL)
        m_logger.Info("RecoveryManager", "Backend confirmed state: " + stateStr);

    return true;
}

//+------------------------------------------------------------------+
//| GetConsecutiveFailures - Return current failure count               |
//+------------------------------------------------------------------+
int CRecoveryManager::GetConsecutiveFailures() const
{
    return m_consecutiveFailures;
}

//+------------------------------------------------------------------+
//| GetLastStableState - Return last known stable state                 |
//+------------------------------------------------------------------+
EAState CRecoveryManager::GetLastStableState() const
{
    return m_lastStableState;
}

//+------------------------------------------------------------------+
//| SetLastStableState - Update last known stable state                 |
//| Called by the main EA loop when a state is successfully reached     |
//+------------------------------------------------------------------+
void CRecoveryManager::SetLastStableState(EAState state)
{
    // Only track meaningful operational states as "stable"
    if(state != STATE_BOOT && state != STATE_CONNECT && state != STATE_DISCONNECTED)
    {
        m_lastStableState = state;
    }
}

//+------------------------------------------------------------------+
//| IsInRecovery - Check if recovery process is currently in progress   |
//+------------------------------------------------------------------+
bool CRecoveryManager::IsInRecovery() const
{
    return m_isInRecovery;
}

#endif // EA_GATEWAY_RECOVERYMANAGER_MQH
