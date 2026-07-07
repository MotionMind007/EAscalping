//+------------------------------------------------------------------+
//|                                              MarketCollector.mqh   |
//|                         EA Gateway - Market Data Collection        |
//|                         Tick batching and candle forwarding         |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_MARKETCOLLECTOR_MQH
#define EA_GATEWAY_MARKETCOLLECTOR_MQH

#include "Types.mqh"
#include "Logger.mqh"
#include "HttpClient.mqh"

//+------------------------------------------------------------------+
//| Constants                                                          |
//+------------------------------------------------------------------+
#define MARKET_MAX_BATCH_SIZE     10      // Maximum ticks per batch
#define MARKET_BATCH_WINDOW_MS    100     // Max ms before flushing batch
#define MARKET_TICK_ENDPOINT      "/api/v1/market/tick"
#define MARKET_CANDLE_ENDPOINT    "/api/v1/market/candle"

//+------------------------------------------------------------------+
//| CMarketCollector - Collects and batches market data for forwarding |
//+------------------------------------------------------------------+
class CMarketCollector
{
private:
    CLogger*      m_logger;              // Pointer to logger instance
    CHttpClient*  m_httpClient;          // Pointer to HTTP client
    string        m_timeframe;           // Configured timeframe string (M1, M5, etc.)
    EAState*      m_statePtr;            // Pointer to current EA state

    //--- Tick batching state
    TickData      m_tickBuffer[];        // Buffer for batching (max 10)
    int           m_tickCount;           // Number of ticks in buffer
    uint          m_batchStartTickMs;    // GetTickCount() at first tick in batch

    //--- Candle state
    CandleData    m_lastCandle;          // Last collected candle data

    //--- Private helpers
    bool          IsStateAllowed();
    string        FormatTimestamp(datetime time);
    string        FormatTimestampMs(datetime time, int milliseconds);
    ENUM_TIMEFRAMES StringToTimeframe(string tf);
    void          FlushTickBatch();
    void          SendTickPayload(string jsonPayload);
    void          SendCandlePayload(string jsonPayload);

public:
    //--- Constructor / Destructor
                  CMarketCollector();
                 ~CMarketCollector();

    //--- Initialization
    void          Init(CLogger* logger, CHttpClient* httpClient, string timeframe, EAState* statePtr);

    //--- Core methods
    void          OnTick();               // Called every tick
    void          OnNewBar();             // Called on bar close

    //--- Serialization (public for testing)
    string        SerializeTickBatch();   // JSON array of ticks in buffer
    string        SerializeCandle();      // JSON single candle

    //--- Batch management
    bool          ShouldFlushBatch();     // true if 10 ticks or 100ms elapsed
    int           GetBufferedTickCount(); // Number of ticks in buffer
};

//+------------------------------------------------------------------+
//| Constructor                                                        |
//+------------------------------------------------------------------+
CMarketCollector::CMarketCollector()
{
    m_logger           = NULL;
    m_httpClient       = NULL;
    m_timeframe        = "M1";
    m_statePtr         = NULL;
    m_tickCount        = 0;
    m_batchStartTickMs = 0;
    ArrayResize(m_tickBuffer, MARKET_MAX_BATCH_SIZE);
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CMarketCollector::~CMarketCollector()
{
    // Not owned, do not delete
    m_logger     = NULL;
    m_httpClient = NULL;
    m_statePtr   = NULL;
}

//+------------------------------------------------------------------+
//| Init - Configure the market collector with dependencies            |
//+------------------------------------------------------------------+
void CMarketCollector::Init(CLogger* logger, CHttpClient* httpClient, string timeframe, EAState* statePtr)
{
    m_logger     = logger;
    m_httpClient = httpClient;
    m_timeframe  = timeframe;
    m_statePtr   = statePtr;
    m_tickCount  = 0;
    m_batchStartTickMs = 0;

    if(m_logger != NULL)
        m_logger.Info("MarketCollector", "Initialized. Timeframe: " + m_timeframe);
}

//+------------------------------------------------------------------+
//| IsStateAllowed - Check if current state allows market collection   |
//| Only collect/forward when state is after CONNECT                   |
//| (not in BOOT or CONNECT)                                           |
//+------------------------------------------------------------------+
bool CMarketCollector::IsStateAllowed()
{
    if(m_statePtr == NULL)
        return false;

    EAState currentState = *m_statePtr;

    // Only allowed after CONNECT state (not BOOT, not CONNECT)
    if(currentState == STATE_BOOT || currentState == STATE_CONNECT)
        return false;

    return true;
}

//+------------------------------------------------------------------+
//| OnTick - Called every tick to collect and batch market data         |
//|                                                                    |
//| Batching rules:                                                    |
//| - Collect bid/ask/spread into buffer                               |
//| - If buffer reaches 10 ticks OR 100ms elapsed since first tick:    |
//|   flush the batch (send HTTP POST)                                 |
//| - If tick rate is low (≤10/sec), flush immediately (batch of 1     |
//|   happens naturally when 100ms elapses with only 1 tick)           |
//+------------------------------------------------------------------+
void CMarketCollector::OnTick()
{
    //--- State guard: only collect after CONNECT
    if(!IsStateAllowed())
        return;

    //--- First, check if existing batch needs flushing due to time
    if(m_tickCount > 0 && ShouldFlushBatch())
    {
        FlushTickBatch();
    }

    //--- Collect current tick data
    TickData tick;
    tick.timestamp = TimeGMT();
    tick.bid       = SymbolInfoDouble(Symbol(), SYMBOL_BID);
    tick.ask       = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
    tick.spread    = (int)SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);

    //--- Add to buffer
    if(m_tickCount < MARKET_MAX_BATCH_SIZE)
    {
        m_tickBuffer[m_tickCount] = tick;
        m_tickCount++;

        // Record batch start time on first tick
        if(m_tickCount == 1)
            m_batchStartTickMs = GetTickCount();
    }

    //--- Check if we should flush now (buffer full)
    if(ShouldFlushBatch())
    {
        FlushTickBatch();
    }
}

//+------------------------------------------------------------------+
//| OnNewBar - Called when a new bar closes on the configured timeframe|
//+------------------------------------------------------------------+
void CMarketCollector::OnNewBar()
{
    //--- State guard: only collect after CONNECT
    if(!IsStateAllowed())
        return;

    //--- Get the timeframe enum
    ENUM_TIMEFRAMES tf = StringToTimeframe(m_timeframe);

    //--- Collect OHLCV for the most recently closed bar (index 1)
    m_lastCandle.timestamp = iTime(Symbol(), tf, 1);
    m_lastCandle.timeframe = m_timeframe;
    m_lastCandle.open      = iOpen(Symbol(), tf, 1);
    m_lastCandle.high      = iHigh(Symbol(), tf, 1);
    m_lastCandle.low       = iLow(Symbol(), tf, 1);
    m_lastCandle.close     = iClose(Symbol(), tf, 1);
    m_lastCandle.volume    = iVolume(Symbol(), tf, 1);

    //--- Serialize and send
    string payload = SerializeCandle();
    SendCandlePayload(payload);
}

//+------------------------------------------------------------------+
//| ShouldFlushBatch - Determine if tick batch should be flushed       |
//| Returns true if:                                                   |
//|   - Buffer has reached max size (10 ticks), OR                     |
//|   - 100ms have elapsed since first tick in batch                   |
//+------------------------------------------------------------------+
bool CMarketCollector::ShouldFlushBatch()
{
    if(m_tickCount <= 0)
        return false;

    // Condition 1: buffer full
    if(m_tickCount >= MARKET_MAX_BATCH_SIZE)
        return true;

    // Condition 2: 100ms elapsed since first tick in batch
    uint elapsed = GetTickCount() - m_batchStartTickMs;
    if(elapsed >= MARKET_BATCH_WINDOW_MS)
        return true;

    return false;
}

//+------------------------------------------------------------------+
//| FlushTickBatch - Serialize buffered ticks and send via HTTP         |
//+------------------------------------------------------------------+
void CMarketCollector::FlushTickBatch()
{
    if(m_tickCount <= 0)
        return;

    //--- Serialize the batch
    string payload = SerializeTickBatch();

    //--- Send via HTTP
    SendTickPayload(payload);

    //--- Reset buffer
    m_tickCount        = 0;
    m_batchStartTickMs = 0;
}

//+------------------------------------------------------------------+
//| SerializeTickBatch - Serialize buffered ticks as JSON payload       |
//| Format: {"symbol":"XAUUSD","ticks":[{...},{...}]}                  |
//+------------------------------------------------------------------+
string CMarketCollector::SerializeTickBatch()
{
    string json = "{\"symbol\":\"" + Symbol() + "\",\"ticks\":[";

    for(int i = 0; i < m_tickCount; i++)
    {
        if(i > 0)
            json += ",";

        // Get milliseconds component from GetTickCount offset
        int milliseconds = (int)(GetTickCount() % 1000);

        string tickJson = "{";
        tickJson += "\"timestamp\":\"" + FormatTimestamp(m_tickBuffer[i].timestamp) + "\",";
        tickJson += "\"bid\":" + DoubleToString(m_tickBuffer[i].bid, 2) + ",";
        tickJson += "\"ask\":" + DoubleToString(m_tickBuffer[i].ask, 2) + ",";
        tickJson += "\"spread\":" + IntegerToString(m_tickBuffer[i].spread);
        tickJson += "}";

        json += tickJson;
    }

    json += "]}";
    return json;
}

//+------------------------------------------------------------------+
//| SerializeCandle - Serialize the last candle as JSON payload         |
//| Format: {"symbol":"XAUUSD","timeframe":"M1","timestamp":"...","open":...}
//+------------------------------------------------------------------+
string CMarketCollector::SerializeCandle()
{
    string json = "{";
    json += "\"symbol\":\"" + Symbol() + "\",";
    json += "\"timeframe\":\"" + m_lastCandle.timeframe + "\",";
    json += "\"timestamp\":\"" + FormatTimestamp(m_lastCandle.timestamp) + "\",";
    json += "\"open\":" + DoubleToString(m_lastCandle.open, 2) + ",";
    json += "\"high\":" + DoubleToString(m_lastCandle.high, 2) + ",";
    json += "\"low\":" + DoubleToString(m_lastCandle.low, 2) + ",";
    json += "\"close\":" + DoubleToString(m_lastCandle.close, 2) + ",";
    json += "\"volume\":" + IntegerToString(m_lastCandle.volume);
    json += "}";
    return json;
}

//+------------------------------------------------------------------+
//| FormatTimestamp - Format datetime as ISO 8601 UTC with ms          |
//| Format: yyyy-MM-ddTHH:mm:ss.fffZ                                  |
//+------------------------------------------------------------------+
string CMarketCollector::FormatTimestamp(datetime time)
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
//| FormatTimestampMs - Format datetime with explicit milliseconds      |
//+------------------------------------------------------------------+
string CMarketCollector::FormatTimestampMs(datetime time, int milliseconds)
{
    MqlDateTime dt;
    TimeToStruct(time, dt);

    string timestamp = StringFormat("%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
                                   dt.year, dt.mon, dt.day,
                                   dt.hour, dt.min, dt.sec,
                                   milliseconds);
    return timestamp;
}

//+------------------------------------------------------------------+
//| StringToTimeframe - Convert string to MQL5 timeframe enum          |
//+------------------------------------------------------------------+
ENUM_TIMEFRAMES CMarketCollector::StringToTimeframe(string tf)
{
    if(tf == "M1")  return PERIOD_M1;
    if(tf == "M5")  return PERIOD_M5;
    if(tf == "M15") return PERIOD_M15;
    if(tf == "H1")  return PERIOD_H1;

    // Default to M1 if unrecognized
    if(m_logger != NULL)
        m_logger.Warn("MarketCollector", "Unrecognized timeframe '" + tf + "', defaulting to M1");
    return PERIOD_M1;
}

//+------------------------------------------------------------------+
//| SendTickPayload - Forward tick batch to backend via HTTP POST       |
//+------------------------------------------------------------------+
void CMarketCollector::SendTickPayload(string jsonPayload)
{
    if(m_httpClient == NULL)
    {
        if(m_logger != NULL)
            m_logger.Error("MarketCollector", "HttpClient is NULL, cannot send tick data");
        return;
    }

    HttpResponse response = m_httpClient.Post(MARKET_TICK_ENDPOINT, jsonPayload);

    if(response.statusCode >= 200 && response.statusCode < 300)
    {
        // Success - no action needed
    }
    else
    {
        if(m_logger != NULL)
            m_logger.Warn("MarketCollector", "Tick POST failed. Status: " +
                         IntegerToString(response.statusCode) +
                         " Latency: " + IntegerToString(response.latencyMs) + "ms");
    }
}

//+------------------------------------------------------------------+
//| SendCandlePayload - Forward candle data to backend via HTTP POST    |
//+------------------------------------------------------------------+
void CMarketCollector::SendCandlePayload(string jsonPayload)
{
    if(m_httpClient == NULL)
    {
        if(m_logger != NULL)
            m_logger.Error("MarketCollector", "HttpClient is NULL, cannot send candle data");
        return;
    }

    HttpResponse response = m_httpClient.Post(MARKET_CANDLE_ENDPOINT, jsonPayload);

    if(response.statusCode >= 200 && response.statusCode < 300)
    {
        if(m_logger != NULL)
            m_logger.Info("MarketCollector", "Candle data sent. Timeframe: " + m_lastCandle.timeframe +
                        " Latency: " + IntegerToString(response.latencyMs) + "ms");
    }
    else
    {
        if(m_logger != NULL)
            m_logger.Warn("MarketCollector", "Candle POST failed. Status: " +
                         IntegerToString(response.statusCode) +
                         " Latency: " + IntegerToString(response.latencyMs) + "ms");
    }
}

//+------------------------------------------------------------------+
//| GetBufferedTickCount - Return number of ticks currently in buffer   |
//+------------------------------------------------------------------+
int CMarketCollector::GetBufferedTickCount()
{
    return m_tickCount;
}

#endif // EA_GATEWAY_MARKETCOLLECTOR_MQH
