//+------------------------------------------------------------------+
//|                                               SessionManager.mqh  |
//|                         EA Gateway - Session Time Enforcement      |
//|                         UTC session window logic                   |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_SESSION_MANAGER_MQH
#define EA_GATEWAY_SESSION_MANAGER_MQH

#include "Types.mqh"

//+------------------------------------------------------------------+
//| CSessionManager - Enforces trading session windows                 |
//|                                                                    |
//| Session definitions (all UTC):                                     |
//|   London:  08:00 - 16:00 (inclusive start, exclusive end)          |
//|   New York: 13:00 - 21:00 (inclusive start, exclusive end)         |
//|   Overlap: 13:00 - 16:00 (both London and NY active)              |
//|   Combined: 08:00 - 21:00 (any active session)                    |
//|                                                                    |
//| Session name logic:                                                |
//|   LONDON:   8 <= H < 13  (London-only, before NY overlap)          |
//|   OVERLAP: 13 <= H < 16  (both London and NY active)               |
//|   NEW_YORK: 16 <= H < 21  (NY-only, after London closes)           |
//|   OFF:      H < 8 or H >= 21                                       |
//+------------------------------------------------------------------+
class CSessionManager
{
private:
    int     m_londonStartHour;   // 8
    int     m_londonEndHour;     // 16
    int     m_nyStartHour;       // 13
    int     m_nyEndHour;         // 21

    //--- Helper
    int     GetCurrentUtcHour();

public:
    //--- Constructor / Destructor
              CSessionManager();
             ~CSessionManager();

    //--- Session queries
    bool      IsInSession();              // true if combined session active [8, 21)
    bool      IsLondonSession();          // true if London session active [8, 16)
    bool      IsNewYorkSession();         // true if New York session active [13, 21)
    string    GetCurrentSessionName();    // "LONDON", "NEW_YORK", "OVERLAP", "OFF"

    //--- Trade permission
    bool      CanOpenTrade();             // true if in session (RISK_LOCK check added later)
    bool      CanCloseTrade();            // always true (close allowed outside session)

    //--- Accessors for testing/configuration
    int       GetLondonStartHour() const  { return m_londonStartHour; }
    int       GetLondonEndHour() const    { return m_londonEndHour; }
    int       GetNYStartHour() const      { return m_nyStartHour; }
    int       GetNYEndHour() const        { return m_nyEndHour; }
};

//+------------------------------------------------------------------+
//| Constructor - Initialize session hour boundaries                   |
//+------------------------------------------------------------------+
CSessionManager::CSessionManager()
{
    m_londonStartHour = 8;
    m_londonEndHour   = 16;
    m_nyStartHour     = 13;
    m_nyEndHour       = 21;
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CSessionManager::~CSessionManager()
{
}

//+------------------------------------------------------------------+
//| GetCurrentUtcHour - Get the current UTC hour from TimeGMT()        |
//+------------------------------------------------------------------+
int CSessionManager::GetCurrentUtcHour()
{
    datetime now = TimeGMT();
    MqlDateTime dt;
    TimeToStruct(now, dt);
    return dt.hour;
}

//+------------------------------------------------------------------+
//| IsInSession - Returns true if current UTC hour is within the       |
//|               combined session window [8, 21)                      |
//|               London OR New York active                            |
//+------------------------------------------------------------------+
bool CSessionManager::IsInSession()
{
    int hour = GetCurrentUtcHour();
    return (hour >= m_londonStartHour && hour < m_nyEndHour);
}

//+------------------------------------------------------------------+
//| IsLondonSession - Returns true if current UTC hour is within       |
//|                   London session [8, 16)                           |
//+------------------------------------------------------------------+
bool CSessionManager::IsLondonSession()
{
    int hour = GetCurrentUtcHour();
    return (hour >= m_londonStartHour && hour < m_londonEndHour);
}

//+------------------------------------------------------------------+
//| IsNewYorkSession - Returns true if current UTC hour is within      |
//|                    New York session [13, 21)                       |
//+------------------------------------------------------------------+
bool CSessionManager::IsNewYorkSession()
{
    int hour = GetCurrentUtcHour();
    return (hour >= m_nyStartHour && hour < m_nyEndHour);
}

//+------------------------------------------------------------------+
//| GetCurrentSessionName - Returns the name of the current session    |
//|                                                                    |
//| Logic:                                                             |
//|   LONDON:    8 <= H < 13 (London-only, before NY starts)           |
//|   OVERLAP:  13 <= H < 16 (both London and NY active)               |
//|   NEW_YORK: 16 <= H < 21 (NY-only, after London closes)            |
//|   OFF:       H < 8 or H >= 21                                      |
//+------------------------------------------------------------------+
string CSessionManager::GetCurrentSessionName()
{
    int hour = GetCurrentUtcHour();

    // Check OFF first (outside any session)
    if(hour < m_londonStartHour || hour >= m_nyEndHour)
        return "OFF";

    // Overlap: both London and NY are active [13, 16)
    if(hour >= m_nyStartHour && hour < m_londonEndHour)
        return "OVERLAP";

    // London-only: [8, 13) - before NY starts
    if(hour >= m_londonStartHour && hour < m_nyStartHour)
        return "LONDON";

    // New York-only: [16, 21) - after London closes
    if(hour >= m_londonEndHour && hour < m_nyEndHour)
        return "NEW_YORK";

    // Should not reach here, but defensive
    return "OFF";
}

//+------------------------------------------------------------------+
//| CanOpenTrade - Returns true if trading is allowed                   |
//|               Currently: only if in session                        |
//|               Future: will also check RISK_LOCK status             |
//+------------------------------------------------------------------+
bool CSessionManager::CanOpenTrade()
{
    return IsInSession();
}

//+------------------------------------------------------------------+
//| CanCloseTrade - Returns true always                                |
//|                 Close is allowed regardless of session time         |
//|                 (positions may need closing after session ends)     |
//+------------------------------------------------------------------+
bool CSessionManager::CanCloseTrade()
{
    return true;
}

#endif // EA_GATEWAY_SESSION_MANAGER_MQH
