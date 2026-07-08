//+------------------------------------------------------------------+
//|                                                       Types.mqh   |
//|                         EA Gateway - Core Types                    |
//|                         Shared enums and structs                   |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_TYPES_MQH
#define EA_GATEWAY_TYPES_MQH

//+------------------------------------------------------------------+
//| EAState - Finite State Machine states                             |
//+------------------------------------------------------------------+
enum EAState
{
    STATE_BOOT,               // Initialization, loading config
    STATE_CONNECT,            // Attempting backend connection
    STATE_WAIT_SESSION,       // Waiting for trading session window
    STATE_CHECK_RISK,         // Checking risk status with backend
    STATE_SCAN_SIGNAL,        // Scanning for trade signals
    STATE_AI_CONFIRMATION,    // Waiting for AI prediction approval
    STATE_OPEN_POSITION,      // Executing trade command
    STATE_MANAGE_POSITION,    // Managing open position
    STATE_POSITION_CLOSED,    // Position closed, reporting result
    STATE_DISCONNECTED        // Backend unreachable
};

//+------------------------------------------------------------------+
//| TradeCommandType - Types of trade commands from the backend        |
//+------------------------------------------------------------------+
enum TradeCommandType
{
    CMD_BUY,                  // Open a BUY market order
    CMD_SELL,                 // Open a SELL market order
    CMD_CLOSE                 // Close an existing position
};

//+------------------------------------------------------------------+
//| TickData - Real-time price update from MT5                         |
//+------------------------------------------------------------------+
struct TickData
{
    datetime timestamp;       // UTC, ISO 8601
    double   bid;             // Bid price
    double   ask;             // Ask price
    int      spread;          // Spread in points
};

//+------------------------------------------------------------------+
//| CandleData - OHLCV bar data from MT5                               |
//+------------------------------------------------------------------+
struct CandleData
{
    datetime timestamp;       // Bar open time, UTC
    string   timeframe;       // "M1", "M5", "M15", "H1"
    double   open;            // Open price
    double   high;            // High price
    double   low;             // Low price
    double   close;           // Close price
    long     volume;          // Tick volume
};

//+------------------------------------------------------------------+
//| TradeCommand - Instruction from backend to execute a trade         |
//+------------------------------------------------------------------+
struct TradeCommand
{
    TradeCommandType type;    // BUY, SELL, or CLOSE
    double           lotSize;      // Lot size for BUY/SELL
    double           stopLoss;     // Stop-loss price level
    double           takeProfit;   // Take-profit price level
    long             ticket;       // Ticket number (for CLOSE commands)
};

//+------------------------------------------------------------------+
//| TradeResult - Execution result reported back to backend            |
//+------------------------------------------------------------------+
struct TradeResult
{
    bool    success;          // Whether execution succeeded
    long    ticket;           // MT5 ticket number
    double  fillPrice;        // Actual fill price
    int     slippagePoints;   // Slippage in points
    int     errorCode;        // MT5 error code if failed
    string  errorMessage;     // Human-readable error description
};

//+------------------------------------------------------------------+
//| HttpResponse - Response from backend HTTP request                   |
//+------------------------------------------------------------------+
struct HttpResponse
{
    int    statusCode;        // HTTP status code
    string body;              // Response body (JSON string)
    int    latencyMs;         // Request round-trip latency in ms
    bool   isValid;           // true if response body is valid JSON
};

//+------------------------------------------------------------------+
//| HeartbeatPayload - Health data sent to backend periodically         |
//+------------------------------------------------------------------+
struct HeartbeatPayload
{
    string   eaState;         // Current EA state as string
    double   accountBalance;  // Account balance
    double   accountEquity;   // Account equity
    int      latencyMs;       // Last backend latency in ms
    bool     mt5Connected;    // MT5 trade server connection status
    int      currentSpread;   // Current spread in points
    datetime lastHeartbeatUtc; // Timestamp of last successful heartbeat
};

#endif // EA_GATEWAY_TYPES_MQH

//+------------------------------------------------------------------+
//| Forward declaration for global state (defined in EAGateway.mq5)    |
//+------------------------------------------------------------------+
// Modules access this directly instead of using pointers
extern EAState g_currentState;
