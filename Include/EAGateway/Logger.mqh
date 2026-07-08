//+------------------------------------------------------------------+
//|                                                      Logger.mqh   |
//|                         EA Gateway - File-Based Logger             |
//|                         UTC timestamp logging with auto-rotation   |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_LOGGER_MQH
#define EA_GATEWAY_LOGGER_MQH

#include "Types.mqh"

//+------------------------------------------------------------------+
//| LogLevel - Severity levels for log entries                         |
//+------------------------------------------------------------------+
enum LogLevel
{
    LOG_INFO,     // Informational messages
    LOG_WARN,     // Warning conditions
    LOG_ERROR,    // Error conditions
    LOG_STATE     // State transition events
};

//+------------------------------------------------------------------+
//| CLogger - File-based logger with UTC timestamps and auto-rotation |
//+------------------------------------------------------------------+
class CLogger
{
private:
    int       m_fileHandle;         // Current log file handle
    string    m_currentFileName;    // Current log file name (for rotation check)
    string    m_logPrefix;          // Log file name prefix
    EAState   m_currentState;       // Current EA state for log context
    int       m_maxFileSizeMB;      // Max file size before rotation (MB)

    //--- Private helpers
    string    GetTimestamp();
    string    LevelToString(LogLevel level);
    string    BuildLogFileName();
    bool      OpenLogFile();
    void      CloseLogFile();
    bool      ShouldRotate();
    void      RotateIfNeeded();

public:
    //--- Constructor / Destructor
              CLogger();
             ~CLogger();

    //--- Initialization
    bool      Init(string prefix = "EAGateway", int maxFileSizeMB = 10);
    void      Deinit();

    //--- State management
    void      SetCurrentState(EAState state);
    EAState   GetCurrentState() const;

    //--- Core logging methods
    void      Log(LogLevel level, string module, string message);
    void      Info(string module, string message);
    void      Warn(string module, string message);
    void      Error(string module, string message);

    //--- State transition logging
    void      LogStateTransition(EAState from, EAState to, string reason);

    //--- Utility
    string    StateToString(EAState state);
};

//+------------------------------------------------------------------+
//| Constructor                                                        |
//+------------------------------------------------------------------+
CLogger::CLogger()
{
    m_fileHandle      = INVALID_HANDLE;
    m_currentFileName = "";
    m_logPrefix       = "EAGateway";
    m_currentState    = STATE_BOOT;
    m_maxFileSizeMB   = 10;
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CLogger::~CLogger()
{
    Deinit();
}

//+------------------------------------------------------------------+
//| Init - Initialize logger with file prefix and max size             |
//+------------------------------------------------------------------+
bool CLogger::Init(string prefix, int maxFileSizeMB)
{
    m_logPrefix     = prefix;
    m_maxFileSizeMB = maxFileSizeMB;

    if(!OpenLogFile())
    {
        Print("CLogger::Init - Failed to open log file");
        return false;
    }

    Info("Logger", "Logger initialized. File: " + m_currentFileName);
    return true;
}

//+------------------------------------------------------------------+
//| Deinit - Clean up resources                                        |
//+------------------------------------------------------------------+
void CLogger::Deinit()
{
    if(m_fileHandle != INVALID_HANDLE)
    {
        Info("Logger", "Logger shutting down");
        CloseLogFile();
    }
}

//+------------------------------------------------------------------+
//| SetCurrentState - Update internal state for log context            |
//+------------------------------------------------------------------+
void CLogger::SetCurrentState(EAState state)
{
    m_currentState = state;
}

//+------------------------------------------------------------------+
//| GetCurrentState - Get the current state stored in logger           |
//+------------------------------------------------------------------+
EAState CLogger::GetCurrentState() const
{
    return m_currentState;
}

//+------------------------------------------------------------------+
//| Log - Main logging method with level, module, and message          |
//| Format: [yyyy-MM-ddTHH:mm:ss.fffZ] [LEVEL] [STATE:xxx] [MODULE:xxx] message
//+------------------------------------------------------------------+
void CLogger::Log(LogLevel level, string module, string message)
{
    RotateIfNeeded();

    string timestamp = GetTimestamp();
    string levelStr  = LevelToString(level);
    string stateStr  = StateToString(m_currentState);

    string logEntry = "[" + timestamp + "] [" + levelStr + "] [STATE:" + stateStr + "] [MODULE:" + module + "] " + message;

    // Write to file
    if(m_fileHandle != INVALID_HANDLE)
    {
        FileWriteString(m_fileHandle, logEntry + "\n");
        FileFlush(m_fileHandle);
    }

    // Also output to MT5 Experts tab for real-time visibility
    Print(logEntry);
}

//+------------------------------------------------------------------+
//| Info - Log informational message                                   |
//+------------------------------------------------------------------+
void CLogger::Info(string module, string message)
{
    Log(LOG_INFO, module, message);
}

//+------------------------------------------------------------------+
//| Warn - Log warning message                                         |
//+------------------------------------------------------------------+
void CLogger::Warn(string module, string message)
{
    Log(LOG_WARN, module, message);
}

//+------------------------------------------------------------------+
//| Error - Log error message                                          |
//+------------------------------------------------------------------+
void CLogger::Error(string module, string message)
{
    Log(LOG_ERROR, module, message);
}

//+------------------------------------------------------------------+
//| LogStateTransition - Log state machine transition                   |
//| Format: [timestamp] [STATE] FROM → TO (reason: xxx)               |
//+------------------------------------------------------------------+
void CLogger::LogStateTransition(EAState from, EAState to, string reason)
{
    RotateIfNeeded();

    string timestamp = GetTimestamp();
    string fromStr   = StateToString(from);
    string toStr     = StateToString(to);

    string logEntry = "[" + timestamp + "] [STATE] " + fromStr + " → " + toStr + " (reason: " + reason + ")";

    // Write to file
    if(m_fileHandle != INVALID_HANDLE)
    {
        FileWriteString(m_fileHandle, logEntry + "\n");
        FileFlush(m_fileHandle);
    }

    // Also output to MT5 Experts tab
    Print(logEntry);
}

//+------------------------------------------------------------------+
//| StateToString - Convert EAState enum to readable string            |
//+------------------------------------------------------------------+
string CLogger::StateToString(EAState state)
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
//| GetTimestamp - Generate UTC ISO 8601 timestamp with milliseconds   |
//| Format: yyyy-MM-ddTHH:mm:ss.fffZ                                  |
//+------------------------------------------------------------------+
string CLogger::GetTimestamp()
{
    datetime now = TimeGMT();
    MqlDateTime dt;
    TimeToStruct(now, dt);

    // Get milliseconds from GetTickCount (best available in MQL5)
    int milliseconds = (int)(GetTickCount() % 1000);

    string timestamp = StringFormat("%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
                                   dt.year, dt.mon, dt.day,
                                   dt.hour, dt.min, dt.sec,
                                   milliseconds);
    return timestamp;
}

//+------------------------------------------------------------------+
//| LevelToString - Convert LogLevel enum to string                    |
//+------------------------------------------------------------------+
string CLogger::LevelToString(LogLevel level)
{
    switch(level)
    {
        case LOG_INFO:  return "INFO";
        case LOG_WARN:  return "WARN";
        case LOG_ERROR: return "ERROR";
        case LOG_STATE: return "STATE";
        default:        return "UNKNOWN";
    }
}

//+------------------------------------------------------------------+
//| BuildLogFileName - Generate log file name with date for rotation   |
//| Format: EAGateway_YYYYMMDD.log                                    |
//+------------------------------------------------------------------+
string CLogger::BuildLogFileName()
{
    datetime now = TimeGMT();
    MqlDateTime dt;
    TimeToStruct(now, dt);

    string fileName = StringFormat("%s_%04d%02d%02d.log",
                                  m_logPrefix, dt.year, dt.mon, dt.day);
    return fileName;
}

//+------------------------------------------------------------------+
//| OpenLogFile - Open or create the log file for writing              |
//+------------------------------------------------------------------+
bool CLogger::OpenLogFile()
{
    m_currentFileName = BuildLogFileName();

    // Open file in common folder with write/read/share access
    // FILE_COMMON places it in the shared MQL5 Files directory
    m_fileHandle = FileOpen(m_currentFileName,
                           FILE_WRITE | FILE_READ | FILE_TXT | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE,
                           '\n',
                           CP_UTF8);

    if(m_fileHandle == INVALID_HANDLE)
    {
        Print("CLogger::OpenLogFile - Failed to open file: " + m_currentFileName +
              " Error: " + IntegerToString(GetLastError()));
        return false;
    }

    // Seek to end of file to append (in case file already exists)
    FileSeek(m_fileHandle, 0, SEEK_END);

    return true;
}

//+------------------------------------------------------------------+
//| CloseLogFile - Close the current log file handle                   |
//+------------------------------------------------------------------+
void CLogger::CloseLogFile()
{
    if(m_fileHandle != INVALID_HANDLE)
    {
        FileClose(m_fileHandle);
        m_fileHandle = INVALID_HANDLE;
    }
}

//+------------------------------------------------------------------+
//| ShouldRotate - Check if rotation is needed (date change or size)   |
//+------------------------------------------------------------------+
bool CLogger::ShouldRotate()
{
    // Check date-based rotation: new day = new file
    string expectedFileName = BuildLogFileName();
    if(expectedFileName != m_currentFileName)
        return true;

    // Check size-based rotation
    if(m_fileHandle != INVALID_HANDLE)
    {
        ulong fileSize = FileSize(m_fileHandle);
        ulong maxBytes = (ulong)m_maxFileSizeMB * 1024 * 1024;
        if(fileSize >= maxBytes)
            return true;
    }

    return false;
}

//+------------------------------------------------------------------+
//| RotateIfNeeded - Perform log rotation if conditions are met        |
//+------------------------------------------------------------------+
void CLogger::RotateIfNeeded()
{
    if(!ShouldRotate())
        return;

    // Close current file
    CloseLogFile();

    // If rotation is due to size (same day), rename with suffix
    string expectedFileName = BuildLogFileName();
    if(expectedFileName == m_currentFileName)
    {
        // Size-based rotation: add numeric suffix
        // The old file keeps its name; new writes go to a suffixed file
        datetime now = TimeGMT();
        MqlDateTime dt;
        TimeToStruct(now, dt);

        m_currentFileName = StringFormat("%s_%04d%02d%02d_%02d%02d%02d.log",
                                        m_logPrefix, dt.year, dt.mon, dt.day,
                                        dt.hour, dt.min, dt.sec);

        m_fileHandle = FileOpen(m_currentFileName,
                               FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE,
                               '\n',
                               CP_UTF8);
    }
    else
    {
        // Date-based rotation: open new daily file
        OpenLogFile();
    }

    if(m_fileHandle != INVALID_HANDLE)
    {
        string timestamp = GetTimestamp();
        FileWriteString(m_fileHandle, "[" + timestamp + "] [INFO] [STATE:" + StateToString(m_currentState) + "] [MODULE:Logger] Log file rotated\n");
        FileFlush(m_fileHandle);
    }
}

#endif // EA_GATEWAY_LOGGER_MQH
