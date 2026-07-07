//+------------------------------------------------------------------+
//|                                            CommandDispatcher.mqh  |
//|                         EA Gateway - Command Parsing & Dispatch    |
//|                         Parses backend responses, routes commands  |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_COMMANDDISPATCHER_MQH
#define EA_GATEWAY_COMMANDDISPATCHER_MQH

#include "Types.mqh"
#include "Logger.mqh"
#include "HttpClient.mqh"
#include "StateMachine.mqh"
#include "SessionManager.mqh"
#include "TradeExecutor.mqh"

//+------------------------------------------------------------------+
//| Constants                                                          |
//+------------------------------------------------------------------+
#define CMD_DISPATCH_TRADE_RESULT_ENDPOINT  "/api/v1/trade/result"
#define CMD_DISPATCH_SESSION_ERROR_CODE     -2

//+------------------------------------------------------------------+
//| CCommandDispatcher - Parses and dispatches trade commands from     |
//|                      backend responses                             |
//|                                                                    |
//| Responsibilities:                                                  |
//|   - Parse Trade_Command JSON from backend response body            |
//|   - Parse state transition responses (approved/rejected)           |
//|   - Route commands through SessionManager filter                   |
//|   - Route validated commands to TradeExecutor                      |
//|   - Report session rejections to backend                           |
//|   - Handle state transitions from backend approval                 |
//+------------------------------------------------------------------+
class CCommandDispatcher
{
private:
    CStateMachine*    m_stateMachine;      // FSM for state transitions
    CSessionManager*  m_sessionManager;    // Session window enforcement
    CTradeExecutor*   m_tradeExecutor;     // Trade execution engine
    CLogger*          m_logger;            // Logging
    CHttpClient*      m_httpClient;        // HTTP for rejection reports

    //--- JSON parsing helpers
    string    ExtractStringValue(const string &json, const string &key);
    double    ExtractDoubleValue(const string &json, const string &key);
    long      ExtractLongValue(const string &json, const string &key);
    bool      ExtractBoolValue(const string &json, const string &key);
    string    ExtractObjectValue(const string &json, const string &key);
    bool      HasKey(const string &json, const string &key);

    //--- Utility helpers
    TradeCommandType StringToCommandType(const string &typeStr);
    string    CommandTypeToString(TradeCommandType type);
    string    GetTimestampUtc();
    void      ReportSessionRejection(TradeCommand &cmd);

public:
    //--- Constructor / Destructor
              CCommandDispatcher();
             ~CCommandDispatcher();

    //--- Initialization
    void      Init(CStateMachine* stateMachine,
                   CSessionManager* sessionManager,
                   CTradeExecutor* tradeExecutor,
                   CLogger* logger,
                   CHttpClient* httpClient);

    //--- Core methods
    bool      ParseTradeCommand(const string &jsonBody, TradeCommand &cmd);
    bool      ParseStateResponse(const string &jsonBody, bool &approved,
                                 string &newState, TradeCommand &cmd, bool &hasCommand);
    bool      DispatchCommand(TradeCommand &cmd);
    void      HandleStateResponse(const string &responseBody);
};

//+------------------------------------------------------------------+
//| Constructor                                                        |
//+------------------------------------------------------------------+
CCommandDispatcher::CCommandDispatcher()
{
    m_stateMachine   = NULL;
    m_sessionManager = NULL;
    m_tradeExecutor  = NULL;
    m_logger         = NULL;
    m_httpClient     = NULL;
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CCommandDispatcher::~CCommandDispatcher()
{
    // All pointers are externally owned, do not delete
    m_stateMachine   = NULL;
    m_sessionManager = NULL;
    m_tradeExecutor  = NULL;
    m_logger         = NULL;
    m_httpClient     = NULL;
}

//+------------------------------------------------------------------+
//| Init - Set all module dependencies                                 |
//+------------------------------------------------------------------+
void CCommandDispatcher::Init(CStateMachine* stateMachine,
                              CSessionManager* sessionManager,
                              CTradeExecutor* tradeExecutor,
                              CLogger* logger,
                              CHttpClient* httpClient)
{
    m_stateMachine   = stateMachine;
    m_sessionManager = sessionManager;
    m_tradeExecutor  = tradeExecutor;
    m_logger         = logger;
    m_httpClient     = httpClient;

    if(m_logger != NULL)
        m_logger.Info("CommandDispatcher", "Initialized with all dependencies");
}

//+------------------------------------------------------------------+
//| ParseTradeCommand - Parse Trade_Command JSON from backend response |
//|                                                                    |
//| Expected JSON format:                                              |
//| {                                                                  |
//|   "type": "BUY",                                                   |
//|   "lot_size": 0.10,                                                |
//|   "stop_loss": 2030.00,                                            |
//|   "take_profit": 2045.00,                                          |
//|   "ticket": 123456789         (optional, for CLOSE commands)       |
//| }                                                                  |
//|                                                                    |
//| Returns true if parsing succeeded, false otherwise                 |
//+------------------------------------------------------------------+
bool CCommandDispatcher::ParseTradeCommand(const string &jsonBody, TradeCommand &cmd)
{
    //--- Initialize command with defaults
    cmd.type       = CMD_BUY;
    cmd.lotSize    = 0.0;
    cmd.stopLoss   = 0.0;
    cmd.takeProfit = 0.0;
    cmd.ticket     = 0;

    //--- Validate input
    if(StringLen(jsonBody) == 0)
    {
        if(m_logger != NULL)
            m_logger.Error("CommandDispatcher", "ParseTradeCommand: empty JSON body");
        return false;
    }

    //--- Extract "type" field (required)
    string typeStr = ExtractStringValue(jsonBody, "type");
    if(StringLen(typeStr) == 0)
    {
        if(m_logger != NULL)
            m_logger.Error("CommandDispatcher", "ParseTradeCommand: missing 'type' field");
        return false;
    }

    //--- Convert type string to enum
    if(typeStr == "BUY")
        cmd.type = CMD_BUY;
    else if(typeStr == "SELL")
        cmd.type = CMD_SELL;
    else if(typeStr == "CLOSE")
        cmd.type = CMD_CLOSE;
    else
    {
        if(m_logger != NULL)
            m_logger.Error("CommandDispatcher", "ParseTradeCommand: unknown type '" + typeStr + "'");
        return false;
    }

    //--- Extract lot_size (required for BUY/SELL)
    cmd.lotSize = ExtractDoubleValue(jsonBody, "lot_size");

    //--- Extract stop_loss (optional, defaults to 0)
    cmd.stopLoss = ExtractDoubleValue(jsonBody, "stop_loss");

    //--- Extract take_profit (optional, defaults to 0)
    cmd.takeProfit = ExtractDoubleValue(jsonBody, "take_profit");

    //--- Extract ticket (required for CLOSE, optional otherwise)
    cmd.ticket = ExtractLongValue(jsonBody, "ticket");

    //--- Validate required fields per command type
    if(cmd.type == CMD_BUY || cmd.type == CMD_SELL)
    {
        if(cmd.lotSize <= 0.0)
        {
            if(m_logger != NULL)
                m_logger.Error("CommandDispatcher", "ParseTradeCommand: invalid lot_size for " + typeStr);
            return false;
        }
    }
    else if(cmd.type == CMD_CLOSE)
    {
        if(cmd.ticket <= 0)
        {
            if(m_logger != NULL)
                m_logger.Error("CommandDispatcher", "ParseTradeCommand: missing ticket for CLOSE");
            return false;
        }
    }

    if(m_logger != NULL)
        m_logger.Info("CommandDispatcher", "Parsed command: type=" + typeStr +
                     " lot=" + DoubleToString(cmd.lotSize, 2) +
                     " sl=" + DoubleToString(cmd.stopLoss, 2) +
                     " tp=" + DoubleToString(cmd.takeProfit, 2) +
                     " ticket=" + IntegerToString(cmd.ticket));

    return true;
}

//+------------------------------------------------------------------+
//| ParseStateResponse - Parse state transition response from backend  |
//|                                                                    |
//| Expected JSON format:                                              |
//| {                                                                  |
//|   "approved": true,                                                |
//|   "new_state": "CHECK_RISK",                                       |
//|   "command": null  OR  { "type": "BUY", ... }                      |
//| }                                                                  |
//|                                                                    |
//| Returns true if parsing succeeded                                  |
//+------------------------------------------------------------------+
bool CCommandDispatcher::ParseStateResponse(const string &jsonBody, bool &approved,
                                            string &newState, TradeCommand &cmd, bool &hasCommand)
{
    //--- Initialize outputs
    approved   = false;
    newState   = "";
    hasCommand = false;

    //--- Validate input
    if(StringLen(jsonBody) == 0)
    {
        if(m_logger != NULL)
            m_logger.Error("CommandDispatcher", "ParseStateResponse: empty JSON body");
        return false;
    }

    //--- Extract "approved" field
    approved = ExtractBoolValue(jsonBody, "approved");

    //--- Extract "new_state" field
    newState = ExtractStringValue(jsonBody, "new_state");

    //--- Extract "command" field (may be null or an object)
    string commandJson = ExtractObjectValue(jsonBody, "command");

    if(StringLen(commandJson) > 0 && commandJson != "null")
    {
        hasCommand = ParseTradeCommand(commandJson, cmd);
    }

    if(m_logger != NULL)
        m_logger.Info("CommandDispatcher", "Parsed state response: approved=" +
                     (approved ? "true" : "false") +
                     " new_state=" + newState +
                     " hasCommand=" + (hasCommand ? "true" : "false"));

    return true;
}

//+------------------------------------------------------------------+
//| DispatchCommand - Route command through session filter and execute  |
//|                                                                    |
//| Logic:                                                             |
//|   1. BUY/SELL: check SessionManager - reject if outside session    |
//|   2. CLOSE: always allow (regardless of session)                   |
//|   3. Call TradeExecutor.ExecuteCommand() for validated commands     |
//|   4. TradeExecutor auto-reports results to backend                 |
//|                                                                    |
//| Returns true if command was dispatched (regardless of execution     |
//| result), false if rejected by session filter                        |
//+------------------------------------------------------------------+
bool CCommandDispatcher::DispatchCommand(TradeCommand &cmd)
{
    //--- Session filter for BUY/SELL commands
    if(cmd.type == CMD_BUY || cmd.type == CMD_SELL)
    {
        if(m_sessionManager != NULL && !m_sessionManager.IsInSession())
        {
            if(m_logger != NULL)
                m_logger.Warn("CommandDispatcher", "Command " + CommandTypeToString(cmd.type) +
                             " rejected: outside session window");

            // Report rejection to backend
            ReportSessionRejection(cmd);
            return false;
        }
    }

    //--- CLOSE commands always pass through (no session filter)
    //--- Execute the command via TradeExecutor
    if(m_tradeExecutor == NULL)
    {
        if(m_logger != NULL)
            m_logger.Error("CommandDispatcher", "Cannot dispatch: TradeExecutor is NULL");
        return false;
    }

    if(m_logger != NULL)
        m_logger.Info("CommandDispatcher", "Dispatching " + CommandTypeToString(cmd.type) +
                     " command to TradeExecutor");

    TradeResult result = m_tradeExecutor.ExecuteCommand(cmd);

    if(m_logger != NULL)
    {
        if(result.success)
            m_logger.Info("CommandDispatcher", "Command executed successfully. Ticket: " +
                         IntegerToString(result.ticket));
        else
            m_logger.Warn("CommandDispatcher", "Command execution failed. Error: " +
                         result.errorMessage);
    }

    return true;
}

//+------------------------------------------------------------------+
//| HandleStateResponse - Process full state transition response        |
//|                                                                    |
//| Called when backend responds to a state transition request.         |
//| Logic:                                                             |
//|   1. Parse approved/rejected status                                |
//|   2. If approved with new_state → transition via StateMachine      |
//|   3. If command is present → DispatchCommand                       |
//|   4. If rejected → log and remain in current state                 |
//+------------------------------------------------------------------+
void CCommandDispatcher::HandleStateResponse(const string &responseBody)
{
    bool approved       = false;
    string newState     = "";
    TradeCommand cmd;
    bool hasCommand     = false;

    //--- Parse the response
    if(!ParseStateResponse(responseBody, approved, newState, cmd, hasCommand))
    {
        if(m_logger != NULL)
            m_logger.Error("CommandDispatcher", "Failed to parse state response");
        return;
    }

    //--- Handle approved transition
    if(approved)
    {
        //--- Transition state if new_state is specified
        if(StringLen(newState) > 0 && m_stateMachine != NULL)
        {
            EAState targetState = m_stateMachine.StringToState(newState);
            bool transitioned = m_stateMachine.TransitionTo(targetState, "Backend approved: " + newState);

            if(transitioned)
            {
                if(m_logger != NULL)
                    m_logger.Info("CommandDispatcher", "State transitioned to " + newState +
                                 " (backend approved)");
            }
            else
            {
                if(m_logger != NULL)
                    m_logger.Warn("CommandDispatcher", "State transition to " + newState +
                                 " rejected by FSM (invalid transition)");
            }
        }

        //--- Dispatch embedded command if present
        if(hasCommand)
        {
            if(m_logger != NULL)
                m_logger.Info("CommandDispatcher", "Dispatching embedded command from state response");
            DispatchCommand(cmd);
        }
    }
    else
    {
        //--- Transition rejected by backend
        if(m_logger != NULL)
            m_logger.Info("CommandDispatcher", "State transition rejected by backend. new_state=" + newState);
    }
}

//+------------------------------------------------------------------+
//| ReportSessionRejection - Report trade rejection due to session     |
//|                          window violation to the backend            |
//|                                                                    |
//| POST /api/v1/trade/result with rejection payload                   |
//+------------------------------------------------------------------+
void CCommandDispatcher::ReportSessionRejection(TradeCommand &cmd)
{
    if(m_httpClient == NULL)
    {
        if(m_logger != NULL)
            m_logger.Error("CommandDispatcher", "Cannot report session rejection: HttpClient is NULL");
        return;
    }

    //--- Build rejection JSON
    string json = "{";
    json += "\"success\":false,";
    json += "\"error_code\":" + IntegerToString(CMD_DISPATCH_SESSION_ERROR_CODE) + ",";
    json += "\"error_message\":\"Trade rejected: outside session window\",";
    json += "\"command_type\":\"" + CommandTypeToString(cmd.type) + "\",";
    json += "\"timestamp\":\"" + GetTimestampUtc() + "\"";
    json += "}";

    //--- Send to backend
    HttpResponse response = m_httpClient.Post(CMD_DISPATCH_TRADE_RESULT_ENDPOINT, json);

    if(response.statusCode >= 200 && response.statusCode < 300)
    {
        if(m_logger != NULL)
            m_logger.Info("CommandDispatcher", "Session rejection reported to backend");
    }
    else
    {
        if(m_logger != NULL)
            m_logger.Error("CommandDispatcher", "Failed to report session rejection. Status: " +
                          IntegerToString(response.statusCode));
    }
}

//+------------------------------------------------------------------+
//| ExtractStringValue - Extract a string value for a given key         |
//| Finds "key":"value" pattern in JSON                                |
//| Returns empty string if key not found                              |
//+------------------------------------------------------------------+
string CCommandDispatcher::ExtractStringValue(const string &json, const string &key)
{
    //--- Build search pattern: "key"
    string searchKey = "\"" + key + "\"";
    int keyPos = StringFind(json, searchKey);

    if(keyPos < 0)
        return "";

    //--- Find the colon after the key
    int colonPos = StringFind(json, ":", keyPos + StringLen(searchKey));
    if(colonPos < 0)
        return "";

    //--- Skip whitespace after colon
    int valueStart = colonPos + 1;
    while(valueStart < StringLen(json))
    {
        string ch = StringSubstr(json, valueStart, 1);
        if(ch != " " && ch != "\t" && ch != "\n" && ch != "\r")
            break;
        valueStart++;
    }

    //--- Check if value is a quoted string
    if(StringSubstr(json, valueStart, 1) == "\"")
    {
        // Find closing quote
        int valueEnd = StringFind(json, "\"", valueStart + 1);
        if(valueEnd < 0)
            return "";

        return StringSubstr(json, valueStart + 1, valueEnd - valueStart - 1);
    }

    return "";
}

//+------------------------------------------------------------------+
//| ExtractDoubleValue - Extract a numeric (double) value for a key    |
//| Finds "key":123.45 pattern in JSON                                 |
//| Returns 0.0 if key not found                                       |
//+------------------------------------------------------------------+
double CCommandDispatcher::ExtractDoubleValue(const string &json, const string &key)
{
    //--- Build search pattern: "key"
    string searchKey = "\"" + key + "\"";
    int keyPos = StringFind(json, searchKey);

    if(keyPos < 0)
        return 0.0;

    //--- Find the colon after the key
    int colonPos = StringFind(json, ":", keyPos + StringLen(searchKey));
    if(colonPos < 0)
        return 0.0;

    //--- Skip whitespace after colon
    int valueStart = colonPos + 1;
    while(valueStart < StringLen(json))
    {
        string ch = StringSubstr(json, valueStart, 1);
        if(ch != " " && ch != "\t" && ch != "\n" && ch != "\r")
            break;
        valueStart++;
    }

    //--- Check for null
    if(StringSubstr(json, valueStart, 4) == "null")
        return 0.0;

    //--- Extract numeric value (ends at comma, }, or whitespace)
    string valueStr = "";
    int pos = valueStart;
    while(pos < StringLen(json))
    {
        string ch = StringSubstr(json, pos, 1);
        if(ch == "," || ch == "}" || ch == "]" || ch == " " || ch == "\n" || ch == "\r" || ch == "\t")
            break;
        valueStr += ch;
        pos++;
    }

    if(StringLen(valueStr) == 0)
        return 0.0;

    return StringToDouble(valueStr);
}

//+------------------------------------------------------------------+
//| ExtractLongValue - Extract an integer (long) value for a key       |
//| Finds "key":123456 pattern in JSON                                 |
//| Returns 0 if key not found                                         |
//+------------------------------------------------------------------+
long CCommandDispatcher::ExtractLongValue(const string &json, const string &key)
{
    //--- Build search pattern: "key"
    string searchKey = "\"" + key + "\"";
    int keyPos = StringFind(json, searchKey);

    if(keyPos < 0)
        return 0;

    //--- Find the colon after the key
    int colonPos = StringFind(json, ":", keyPos + StringLen(searchKey));
    if(colonPos < 0)
        return 0;

    //--- Skip whitespace after colon
    int valueStart = colonPos + 1;
    while(valueStart < StringLen(json))
    {
        string ch = StringSubstr(json, valueStart, 1);
        if(ch != " " && ch != "\t" && ch != "\n" && ch != "\r")
            break;
        valueStart++;
    }

    //--- Check for null
    if(StringSubstr(json, valueStart, 4) == "null")
        return 0;

    //--- Extract numeric value (ends at comma, }, or whitespace)
    string valueStr = "";
    int pos = valueStart;
    while(pos < StringLen(json))
    {
        string ch = StringSubstr(json, pos, 1);
        if(ch == "," || ch == "}" || ch == "]" || ch == " " || ch == "\n" || ch == "\r" || ch == "\t")
            break;
        valueStr += ch;
        pos++;
    }

    if(StringLen(valueStr) == 0)
        return 0;

    return StringToInteger(valueStr);
}

//+------------------------------------------------------------------+
//| ExtractBoolValue - Extract a boolean value for a key               |
//| Finds "key":true or "key":false pattern                            |
//| Returns false if key not found                                     |
//+------------------------------------------------------------------+
bool CCommandDispatcher::ExtractBoolValue(const string &json, const string &key)
{
    //--- Build search pattern: "key"
    string searchKey = "\"" + key + "\"";
    int keyPos = StringFind(json, searchKey);

    if(keyPos < 0)
        return false;

    //--- Find the colon after the key
    int colonPos = StringFind(json, ":", keyPos + StringLen(searchKey));
    if(colonPos < 0)
        return false;

    //--- Skip whitespace after colon
    int valueStart = colonPos + 1;
    while(valueStart < StringLen(json))
    {
        string ch = StringSubstr(json, valueStart, 1);
        if(ch != " " && ch != "\t" && ch != "\n" && ch != "\r")
            break;
        valueStart++;
    }

    //--- Check for "true"
    if(StringSubstr(json, valueStart, 4) == "true")
        return true;

    return false;
}

//+------------------------------------------------------------------+
//| ExtractObjectValue - Extract a nested JSON object for a key        |
//| Finds "key":{...} pattern and returns the inner JSON               |
//| Returns empty string if key not found or value is null             |
//+------------------------------------------------------------------+
string CCommandDispatcher::ExtractObjectValue(const string &json, const string &key)
{
    //--- Build search pattern: "key"
    string searchKey = "\"" + key + "\"";
    int keyPos = StringFind(json, searchKey);

    if(keyPos < 0)
        return "";

    //--- Find the colon after the key
    int colonPos = StringFind(json, ":", keyPos + StringLen(searchKey));
    if(colonPos < 0)
        return "";

    //--- Skip whitespace after colon
    int valueStart = colonPos + 1;
    while(valueStart < StringLen(json))
    {
        string ch = StringSubstr(json, valueStart, 1);
        if(ch != " " && ch != "\t" && ch != "\n" && ch != "\r")
            break;
        valueStart++;
    }

    //--- Check for null
    if(StringSubstr(json, valueStart, 4) == "null")
        return "null";

    //--- Check for object start '{'
    if(StringSubstr(json, valueStart, 1) != "{")
        return "";

    //--- Find matching closing brace (handles nested objects)
    int depth = 0;
    int pos = valueStart;
    while(pos < StringLen(json))
    {
        string ch = StringSubstr(json, pos, 1);
        if(ch == "{")
            depth++;
        else if(ch == "}")
        {
            depth--;
            if(depth == 0)
            {
                // Return the complete object including braces
                return StringSubstr(json, valueStart, pos - valueStart + 1);
            }
        }
        pos++;
    }

    return "";
}

//+------------------------------------------------------------------+
//| HasKey - Check if a key exists in the JSON string                  |
//+------------------------------------------------------------------+
bool CCommandDispatcher::HasKey(const string &json, const string &key)
{
    string searchKey = "\"" + key + "\"";
    return (StringFind(json, searchKey) >= 0);
}

//+------------------------------------------------------------------+
//| StringToCommandType - Convert string to TradeCommandType enum      |
//+------------------------------------------------------------------+
TradeCommandType CCommandDispatcher::StringToCommandType(const string &typeStr)
{
    if(typeStr == "BUY")   return CMD_BUY;
    if(typeStr == "SELL")  return CMD_SELL;
    if(typeStr == "CLOSE") return CMD_CLOSE;
    return CMD_BUY;  // Default fallback
}

//+------------------------------------------------------------------+
//| CommandTypeToString - Convert TradeCommandType to string            |
//+------------------------------------------------------------------+
string CCommandDispatcher::CommandTypeToString(TradeCommandType type)
{
    switch(type)
    {
        case CMD_BUY:   return "BUY";
        case CMD_SELL:  return "SELL";
        case CMD_CLOSE: return "CLOSE";
        default:        return "UNKNOWN";
    }
}

//+------------------------------------------------------------------+
//| GetTimestampUtc - Generate ISO 8601 UTC timestamp                  |
//| Format: yyyy-MM-ddTHH:mm:ss.fffZ                                  |
//+------------------------------------------------------------------+
string CCommandDispatcher::GetTimestampUtc()
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

#endif // EA_GATEWAY_COMMANDDISPATCHER_MQH
