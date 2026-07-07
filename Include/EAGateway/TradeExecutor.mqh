//+------------------------------------------------------------------+
//|                                                TradeExecutor.mqh  |
//|                         EA Gateway - Trade Execution Module        |
//|                         Validates and executes trade commands      |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_TRADEEXECUTOR_MQH
#define EA_GATEWAY_TRADEEXECUTOR_MQH

#include "Types.mqh"
#include "Logger.mqh"
#include "HttpClient.mqh"
#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Constants                                                          |
//+------------------------------------------------------------------+
#define TRADE_LOT_MIN            0.01     // Minimum lot size
#define TRADE_LOT_MAX            100.0    // Maximum lot size
#define TRADE_RESULT_ENDPOINT    "/api/v1/trade/result"
#define TRADE_REPORT_TIMEOUT_MS  200      // Maximum time to report result

//+------------------------------------------------------------------+
//| CTradeExecutor - Validates and executes trade commands              |
//+------------------------------------------------------------------+
class CTradeExecutor
{
private:
    CLogger*      m_logger;            // Pointer to logger instance
    CHttpClient*  m_httpClient;        // Pointer to HTTP client
    CTrade        m_trade;             // MQL5 trade object
    bool          m_hasOpenPosition;   // Whether a position is currently open
    long          m_openTicket;        // Ticket of the open position

    //--- Private validation helpers
    bool          ValidateLotSize(double lots);
    bool          ValidateStopLevels(double sl, double tp, TradeCommandType type);
    bool          CheckNoExistingPosition(TradeCommandType type);
    bool          CheckTicketMatchesOpen(long ticket);

    //--- Private execution helpers
    TradeResult   ExecuteBuy(TradeCommand &cmd);
    TradeResult   ExecuteSell(TradeCommand &cmd);
    TradeResult   ExecuteClose(TradeCommand &cmd);

    //--- Result reporting
    void          ReportResult(TradeResult &result, TradeCommandType cmdType);
    string        BuildResultJson(TradeResult &result, TradeCommandType cmdType);
    string        CommandTypeToString(TradeCommandType type);
    string        GetTimestampUtc();

public:
    //--- Constructor / Destructor
                  CTradeExecutor();
                 ~CTradeExecutor();

    //--- Initialization
    void          Init(CLogger* logger, CHttpClient* httpClient);

    //--- Core methods
    TradeResult   ExecuteCommand(TradeCommand &cmd);
    bool          ValidateCommand(TradeCommand &cmd, string &errorReason);

    //--- Accessors
    bool          HasOpenPosition();
    long          GetOpenTicket();
};

//+------------------------------------------------------------------+
//| Constructor                                                        |
//+------------------------------------------------------------------+
CTradeExecutor::CTradeExecutor()
{
    m_logger          = NULL;
    m_httpClient      = NULL;
    m_hasOpenPosition = false;
    m_openTicket      = 0;
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CTradeExecutor::~CTradeExecutor()
{
    m_logger     = NULL;
    m_httpClient = NULL;
}

//+------------------------------------------------------------------+
//| Init - Set logger and HTTP client references                       |
//+------------------------------------------------------------------+
void CTradeExecutor::Init(CLogger* logger, CHttpClient* httpClient)
{
    m_logger     = logger;
    m_httpClient = httpClient;

    // Configure trade object
    m_trade.SetExpertMagicNumber(123456);
    m_trade.SetDeviationInPoints(10);
    m_trade.SetTypeFilling(ORDER_FILLING_IOC);

    // Check for any existing open position on the symbol at startup
    if(PositionSelect(Symbol()))
    {
        m_hasOpenPosition = true;
        m_openTicket      = (long)PositionGetInteger(POSITION_TICKET);

        if(m_logger != NULL)
            m_logger.Info("TradeExecutor", "Existing position detected at init. Ticket: " +
                         IntegerToString(m_openTicket));
    }
}

//+------------------------------------------------------------------+
//| ValidateCommand - Validate trade command before execution           |
//| Returns true if valid, false with errorReason if invalid            |
//+------------------------------------------------------------------+
bool CTradeExecutor::ValidateCommand(TradeCommand &cmd, string &errorReason)
{
    //--- BUY/SELL validation
    if(cmd.type == CMD_BUY || cmd.type == CMD_SELL)
    {
        // Validate lot size [0.01, 100.0]
        if(!ValidateLotSize(cmd.lotSize))
        {
            errorReason = "Invalid lot size: " + DoubleToString(cmd.lotSize, 2) +
                          ". Must be between " + DoubleToString(TRADE_LOT_MIN, 2) +
                          " and " + DoubleToString(TRADE_LOT_MAX, 2);
            return false;
        }

        // Validate SL/TP price levels
        if(!ValidateStopLevels(cmd.stopLoss, cmd.takeProfit, cmd.type))
        {
            errorReason = "Invalid SL/TP levels. SL: " + DoubleToString(cmd.stopLoss, 2) +
                          ", TP: " + DoubleToString(cmd.takeProfit, 2);
            return false;
        }

        // Check no existing open position
        if(!CheckNoExistingPosition(cmd.type))
        {
            errorReason = "Position already open. Ticket: " + IntegerToString(m_openTicket) +
                          ". Cannot open new " + CommandTypeToString(cmd.type) + " position";
            return false;
        }
    }
    //--- CLOSE validation
    else if(cmd.type == CMD_CLOSE)
    {
        if(!CheckTicketMatchesOpen(cmd.ticket))
        {
            errorReason = "Ticket " + IntegerToString(cmd.ticket) +
                          " does not match any open position";
            return false;
        }
    }

    return true;
}

//+------------------------------------------------------------------+
//| ExecuteCommand - Validate and execute a trade command               |
//| Returns TradeResult with success/failure details                    |
//+------------------------------------------------------------------+
TradeResult CTradeExecutor::ExecuteCommand(TradeCommand &cmd)
{
    TradeResult result;
    result.success        = false;
    result.ticket         = 0;
    result.fillPrice      = 0.0;
    result.slippagePoints = 0;
    result.errorCode      = 0;
    result.errorMessage   = "";

    //--- Validate first
    string errorReason = "";
    if(!ValidateCommand(cmd, errorReason))
    {
        result.errorCode    = -1;
        result.errorMessage = errorReason;

        if(m_logger != NULL)
            m_logger.Error("TradeExecutor", "Command validation failed: " + errorReason);

        // Report failure to backend
        ReportResult(result, cmd.type);
        return result;
    }

    //--- Execute based on command type
    switch(cmd.type)
    {
        case CMD_BUY:
            result = ExecuteBuy(cmd);
            break;
        case CMD_SELL:
            result = ExecuteSell(cmd);
            break;
        case CMD_CLOSE:
            result = ExecuteClose(cmd);
            break;
    }

    //--- Report result to backend
    ReportResult(result, cmd.type);

    return result;
}

//+------------------------------------------------------------------+
//| ExecuteBuy - Execute a BUY market order                             |
//+------------------------------------------------------------------+
TradeResult CTradeExecutor::ExecuteBuy(TradeCommand &cmd)
{
    TradeResult result;
    result.success        = false;
    result.ticket         = 0;
    result.fillPrice      = 0.0;
    result.slippagePoints = 0;
    result.errorCode      = 0;
    result.errorMessage   = "";

    double askPrice = SymbolInfoDouble(Symbol(), SYMBOL_ASK);

    if(m_logger != NULL)
        m_logger.Info("TradeExecutor", "Executing BUY: " + DoubleToString(cmd.lotSize, 2) +
                     " lots at ask " + DoubleToString(askPrice, 2) +
                     " SL=" + DoubleToString(cmd.stopLoss, 2) +
                     " TP=" + DoubleToString(cmd.takeProfit, 2));

    //--- Execute buy using CTrade
    bool success = m_trade.Buy(cmd.lotSize, Symbol(), askPrice, cmd.stopLoss, cmd.takeProfit);

    if(success && m_trade.ResultRetcode() == TRADE_RETCODE_DONE)
    {
        result.success   = true;
        result.ticket    = (long)m_trade.ResultOrder();
        result.fillPrice = m_trade.ResultPrice();

        // Calculate slippage in points
        double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
        if(point > 0)
            result.slippagePoints = (int)MathRound(MathAbs(result.fillPrice - askPrice) / point);

        // Track open position
        m_hasOpenPosition = true;
        m_openTicket      = result.ticket;

        if(m_logger != NULL)
            m_logger.Info("TradeExecutor", "BUY executed. Ticket: " + IntegerToString(result.ticket) +
                         " Fill: " + DoubleToString(result.fillPrice, 2) +
                         " Slippage: " + IntegerToString(result.slippagePoints) + " pts");
    }
    else
    {
        result.errorCode    = (int)m_trade.ResultRetcode();
        result.errorMessage = m_trade.ResultRetcodeDescription();

        if(m_logger != NULL)
            m_logger.Error("TradeExecutor", "BUY failed. Code: " + IntegerToString(result.errorCode) +
                          " Message: " + result.errorMessage);
    }

    return result;
}

//+------------------------------------------------------------------+
//| ExecuteSell - Execute a SELL market order                           |
//+------------------------------------------------------------------+
TradeResult CTradeExecutor::ExecuteSell(TradeCommand &cmd)
{
    TradeResult result;
    result.success        = false;
    result.ticket         = 0;
    result.fillPrice      = 0.0;
    result.slippagePoints = 0;
    result.errorCode      = 0;
    result.errorMessage   = "";

    double bidPrice = SymbolInfoDouble(Symbol(), SYMBOL_BID);

    if(m_logger != NULL)
        m_logger.Info("TradeExecutor", "Executing SELL: " + DoubleToString(cmd.lotSize, 2) +
                     " lots at bid " + DoubleToString(bidPrice, 2) +
                     " SL=" + DoubleToString(cmd.stopLoss, 2) +
                     " TP=" + DoubleToString(cmd.takeProfit, 2));

    //--- Execute sell using CTrade
    bool success = m_trade.Sell(cmd.lotSize, Symbol(), bidPrice, cmd.stopLoss, cmd.takeProfit);

    if(success && m_trade.ResultRetcode() == TRADE_RETCODE_DONE)
    {
        result.success   = true;
        result.ticket    = (long)m_trade.ResultOrder();
        result.fillPrice = m_trade.ResultPrice();

        // Calculate slippage in points
        double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
        if(point > 0)
            result.slippagePoints = (int)MathRound(MathAbs(result.fillPrice - bidPrice) / point);

        // Track open position
        m_hasOpenPosition = true;
        m_openTicket      = result.ticket;

        if(m_logger != NULL)
            m_logger.Info("TradeExecutor", "SELL executed. Ticket: " + IntegerToString(result.ticket) +
                         " Fill: " + DoubleToString(result.fillPrice, 2) +
                         " Slippage: " + IntegerToString(result.slippagePoints) + " pts");
    }
    else
    {
        result.errorCode    = (int)m_trade.ResultRetcode();
        result.errorMessage = m_trade.ResultRetcodeDescription();

        if(m_logger != NULL)
            m_logger.Error("TradeExecutor", "SELL failed. Code: " + IntegerToString(result.errorCode) +
                          " Message: " + result.errorMessage);
    }

    return result;
}

//+------------------------------------------------------------------+
//| ExecuteClose - Close an existing position by ticket                 |
//+------------------------------------------------------------------+
TradeResult CTradeExecutor::ExecuteClose(TradeCommand &cmd)
{
    TradeResult result;
    result.success        = false;
    result.ticket         = 0;
    result.fillPrice      = 0.0;
    result.slippagePoints = 0;
    result.errorCode      = 0;
    result.errorMessage   = "";

    if(m_logger != NULL)
        m_logger.Info("TradeExecutor", "Executing CLOSE for ticket: " + IntegerToString(cmd.ticket));

    //--- Close position using CTrade
    bool success = m_trade.PositionClose((ulong)cmd.ticket);

    if(success && m_trade.ResultRetcode() == TRADE_RETCODE_DONE)
    {
        result.success   = true;
        result.ticket    = cmd.ticket;
        result.fillPrice = m_trade.ResultPrice();

        // Calculate slippage from current price
        double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
        if(point > 0 && PositionSelectByTicket((ulong)cmd.ticket) == false)
        {
            // Position already closed, slippage is based on fill vs expected
            // For close, use bid (if was BUY) or ask (if was SELL)
            result.slippagePoints = 0;  // Slippage calculated from fill price vs request
        }

        // Clear open position tracking
        m_hasOpenPosition = false;
        m_openTicket      = 0;

        if(m_logger != NULL)
            m_logger.Info("TradeExecutor", "CLOSE executed. Ticket: " + IntegerToString(result.ticket) +
                         " Fill: " + DoubleToString(result.fillPrice, 2));
    }
    else
    {
        result.errorCode    = (int)m_trade.ResultRetcode();
        result.errorMessage = m_trade.ResultRetcodeDescription();

        if(m_logger != NULL)
            m_logger.Error("TradeExecutor", "CLOSE failed. Code: " + IntegerToString(result.errorCode) +
                          " Message: " + result.errorMessage);
    }

    return result;
}

//+------------------------------------------------------------------+
//| ValidateLotSize - Check lot size is within [0.01, 100.0]           |
//+------------------------------------------------------------------+
bool CTradeExecutor::ValidateLotSize(double lots)
{
    return (lots >= TRADE_LOT_MIN && lots <= TRADE_LOT_MAX);
}

//+------------------------------------------------------------------+
//| ValidateStopLevels - Validate SL/TP relative to current price      |
//| BUY: SL < ask, TP > ask (with minimum stop distance)              |
//| SELL: SL > bid, TP < bid (with minimum stop distance)             |
//+------------------------------------------------------------------+
bool CTradeExecutor::ValidateStopLevels(double sl, double tp, TradeCommandType type)
{
    //--- Get current prices
    double ask   = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
    double bid   = SymbolInfoDouble(Symbol(), SYMBOL_BID);
    double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);

    //--- Get minimum stop distance in points
    long stopsLevel = SymbolInfoInteger(Symbol(), SYMBOL_TRADE_STOPS_LEVEL);
    double minDistance = stopsLevel * point;

    //--- If SL and TP are both 0, they are optional (no SL/TP set)
    if(sl == 0.0 && tp == 0.0)
        return true;

    if(type == CMD_BUY)
    {
        // SL must be below ask price (with minimum distance)
        if(sl != 0.0)
        {
            if(sl >= ask || (ask - sl) < minDistance)
                return false;
        }
        // TP must be above ask price (with minimum distance)
        if(tp != 0.0)
        {
            if(tp <= ask || (tp - ask) < minDistance)
                return false;
        }
    }
    else if(type == CMD_SELL)
    {
        // SL must be above bid price (with minimum distance)
        if(sl != 0.0)
        {
            if(sl <= bid || (sl - bid) < minDistance)
                return false;
        }
        // TP must be below bid price (with minimum distance)
        if(tp != 0.0)
        {
            if(tp >= bid || (bid - tp) < minDistance)
                return false;
        }
    }

    return true;
}

//+------------------------------------------------------------------+
//| CheckNoExistingPosition - Reject BUY/SELL if position already open |
//+------------------------------------------------------------------+
bool CTradeExecutor::CheckNoExistingPosition(TradeCommandType type)
{
    // Only BUY/SELL are rejected if position exists
    if(type == CMD_BUY || type == CMD_SELL)
    {
        return !m_hasOpenPosition;
    }
    return true;
}

//+------------------------------------------------------------------+
//| CheckTicketMatchesOpen - Verify CLOSE ticket matches open position  |
//+------------------------------------------------------------------+
bool CTradeExecutor::CheckTicketMatchesOpen(long ticket)
{
    if(!m_hasOpenPosition)
        return false;

    return (ticket == m_openTicket);
}

//+------------------------------------------------------------------+
//| ReportResult - Send execution result to backend via HTTP POST       |
//| Must complete within 200ms                                         |
//+------------------------------------------------------------------+
void CTradeExecutor::ReportResult(TradeResult &result, TradeCommandType cmdType)
{
    if(m_httpClient == NULL)
    {
        if(m_logger != NULL)
            m_logger.Error("TradeExecutor", "Cannot report result: HttpClient is NULL");
        return;
    }

    string jsonPayload = BuildResultJson(result, cmdType);

    uint startTime = GetTickCount();

    HttpResponse response = m_httpClient.Post(TRADE_RESULT_ENDPOINT, jsonPayload);

    uint elapsed = GetTickCount() - startTime;

    if(elapsed > TRADE_REPORT_TIMEOUT_MS)
    {
        if(m_logger != NULL)
            m_logger.Warn("TradeExecutor", "Result report exceeded 200ms timeout. Took: " +
                         IntegerToString((int)elapsed) + "ms");
    }

    if(response.statusCode >= 200 && response.statusCode < 300)
    {
        if(m_logger != NULL)
            m_logger.Info("TradeExecutor", "Result reported successfully in " +
                         IntegerToString((int)elapsed) + "ms");
    }
    else
    {
        if(m_logger != NULL)
            m_logger.Error("TradeExecutor", "Failed to report result. Status: " +
                          IntegerToString(response.statusCode) + " Latency: " +
                          IntegerToString((int)elapsed) + "ms");
    }
}

//+------------------------------------------------------------------+
//| BuildResultJson - Serialize TradeResult to JSON for backend         |
//+------------------------------------------------------------------+
string CTradeExecutor::BuildResultJson(TradeResult &result, TradeCommandType cmdType)
{
    string json = "{";

    json += "\"success\":" + (result.success ? "true" : "false") + ",";

    if(result.success)
    {
        json += "\"ticket\":" + IntegerToString(result.ticket) + ",";
        json += "\"fill_price\":" + DoubleToString(result.fillPrice, 2) + ",";
        json += "\"slippage_points\":" + IntegerToString(result.slippagePoints) + ",";
    }
    else
    {
        json += "\"error_code\":" + IntegerToString(result.errorCode) + ",";
        json += "\"error_message\":\"" + result.errorMessage + "\",";
    }

    json += "\"command_type\":\"" + CommandTypeToString(cmdType) + "\",";
    json += "\"timestamp\":\"" + GetTimestampUtc() + "\"";

    json += "}";

    return json;
}

//+------------------------------------------------------------------+
//| CommandTypeToString - Convert enum to string for JSON               |
//+------------------------------------------------------------------+
string CTradeExecutor::CommandTypeToString(TradeCommandType type)
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
string CTradeExecutor::GetTimestampUtc()
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
//| HasOpenPosition - Check if a position is currently open             |
//+------------------------------------------------------------------+
bool CTradeExecutor::HasOpenPosition()
{
    return m_hasOpenPosition;
}

//+------------------------------------------------------------------+
//| GetOpenTicket - Get the ticket of the currently open position       |
//+------------------------------------------------------------------+
long CTradeExecutor::GetOpenTicket()
{
    return m_openTicket;
}

#endif // EA_GATEWAY_TRADEEXECUTOR_MQH
