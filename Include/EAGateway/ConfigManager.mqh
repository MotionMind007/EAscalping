//+------------------------------------------------------------------+
//|                                                ConfigManager.mqh   |
//|                         EA Gateway - Configuration Manager          |
//|                         Loads and validates input parameters        |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_CONFIG_MANAGER_MQH
#define EA_GATEWAY_CONFIG_MANAGER_MQH

#include "Types.mqh"
#include "Inputs.mqh"

//+------------------------------------------------------------------+
//| CConfigManager - Loads and validates EA input parameters           |
//|                                                                    |
//| Validates all configurable inputs at startup. If any validation    |
//| fails, the EA remains in BOOT state and does not proceed.          |
//+------------------------------------------------------------------+
class CConfigManager
{
private:
    string  m_backendUrl;
    string  m_authToken;
    int     m_heartbeatInterval;
    int     m_httpTimeout;
    int     m_maxRetries;
    string  m_timeframe;
    int     m_readTimeout;
    string  m_validationError;

    bool    ValidateUrl(const string url);
    bool    ValidateAuthToken(const string token);
    bool    ValidateHeartbeatInterval(int value);
    bool    ValidateHttpTimeout(int value);
    bool    ValidateMaxRetries(int value);
    bool    ValidateTimeframe(const string tf);
    bool    ValidateReadTimeout(int value);

public:
                CConfigManager();
               ~CConfigManager();

    bool        LoadAndValidate();
    string      GetValidationError();

    // Accessors
    string      GetBackendUrl();
    string      GetAuthToken();
    int         GetHeartbeatInterval();
    int         GetHttpTimeout();
    int         GetMaxRetries();
    string      GetTimeframe();
    int         GetReadTimeout();
};

//+------------------------------------------------------------------+
//| Constructor                                                         |
//+------------------------------------------------------------------+
CConfigManager::CConfigManager()
    : m_backendUrl("")
    , m_authToken("")
    , m_heartbeatInterval(30)
    , m_httpTimeout(5)
    , m_maxRetries(3)
    , m_timeframe("M1")
    , m_readTimeout(10)
    , m_validationError("")
{
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CConfigManager::~CConfigManager()
{
}

//+------------------------------------------------------------------+
//| LoadAndValidate - Load inputs and validate all parameters          |
//| Returns: true if all validations pass, false otherwise             |
//+------------------------------------------------------------------+
bool CConfigManager::LoadAndValidate()
{
    m_validationError = "";

    // Validate Backend URL (Req 8.1, 8.6)
    if(!ValidateUrl(InpBackendUrl))
        return false;

    // Validate Auth Token (Req 8.2, 8.6)
    if(!ValidateAuthToken(InpAuthToken))
        return false;

    // Validate Heartbeat Interval (Req 8.3, 8.7)
    if(!ValidateHeartbeatInterval(InpHeartbeatSec))
        return false;

    // Validate HTTP Timeout (Req 8.4, 8.7)
    if(!ValidateHttpTimeout(InpHttpTimeoutSec))
        return false;

    // Validate Max Retries (Req 8.5, 8.7)
    if(!ValidateMaxRetries(InpMaxRetries))
        return false;

    // Validate Timeframe (Req 8.7)
    if(!ValidateTimeframe(InpTimeframe))
        return false;

    // Validate Read Timeout (Req 8.7)
    if(!ValidateReadTimeout(InpReadTimeoutSec))
        return false;

    // All validations passed - store values
    m_backendUrl        = InpBackendUrl;
    m_authToken         = InpAuthToken;
    m_heartbeatInterval = InpHeartbeatSec;
    m_httpTimeout       = InpHttpTimeoutSec;
    m_maxRetries        = InpMaxRetries;
    m_timeframe         = InpTimeframe;
    m_readTimeout       = InpReadTimeoutSec;

    return true;
}

//+------------------------------------------------------------------+
//| ValidateUrl - Check URL is well-formed HTTP/HTTPS, max 2048 chars  |
//| Req 8.1: well-formed HTTP or HTTPS URL with max 2048 characters    |
//| Req 8.6: if missing, log error with parameter name                 |
//+------------------------------------------------------------------+
bool CConfigManager::ValidateUrl(const string url)
{
    // Check for missing/empty URL
    if(url == NULL || StringLen(url) == 0)
    {
        m_validationError = "BackendUrl: required parameter is missing";
        return false;
    }

    // Check max length
    if(StringLen(url) > 2048)
    {
        m_validationError = "BackendUrl: exceeds maximum length of 2048 characters";
        return false;
    }

    // Check well-formed: must start with http:// or https://
    string urlLower = url;
    StringToLower(urlLower);

    if(StringFind(urlLower, "http://") != 0 && StringFind(urlLower, "https://") != 0)
    {
        m_validationError = "BackendUrl: must start with http:// or https://";
        return false;
    }

    // Check that there is content after the protocol prefix
    int protocolLen = 0;
    if(StringFind(urlLower, "https://") == 0)
        protocolLen = 8;  // "https://" length
    else
        protocolLen = 7;  // "http://" length

    if(StringLen(url) <= protocolLen)
    {
        m_validationError = "BackendUrl: URL has no host after protocol";
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| ValidateAuthToken - Check token is non-empty, max 512 chars        |
//| Req 8.2: non-empty string with max 512 characters                  |
//| Req 8.6: if missing, log error with parameter name                 |
//+------------------------------------------------------------------+
bool CConfigManager::ValidateAuthToken(const string token)
{
    // Check for missing/empty token
    if(token == NULL || StringLen(token) == 0)
    {
        m_validationError = "AuthToken: required parameter is missing";
        return false;
    }

    // Check max length
    if(StringLen(token) > 512)
    {
        m_validationError = "AuthToken: exceeds maximum length of 512 characters";
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| ValidateHeartbeatInterval - Default 30, range [5, 300]             |
//| Req 8.3: default 30, valid range 5 to 300                          |
//+------------------------------------------------------------------+
bool CConfigManager::ValidateHeartbeatInterval(int value)
{
    if(value < 5 || value > 300)
    {
        m_validationError = "HeartbeatInterval: value " + IntegerToString(value) +
                            " is outside valid range [5, 300]";
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| ValidateHttpTimeout - Default 5, range [1, 60]                     |
//| Req 8.4: default 5, valid range 1 to 60                            |
//+------------------------------------------------------------------+
bool CConfigManager::ValidateHttpTimeout(int value)
{
    if(value < 1 || value > 60)
    {
        m_validationError = "HttpTimeout: value " + IntegerToString(value) +
                            " is outside valid range [1, 60]";
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| ValidateMaxRetries - Default 3, range [0, 10]                      |
//| Req 8.5: default 3, valid range 0 to 10                            |
//+------------------------------------------------------------------+
bool CConfigManager::ValidateMaxRetries(int value)
{
    if(value < 0 || value > 10)
    {
        m_validationError = "MaxRetries: value " + IntegerToString(value) +
                            " is outside valid range [0, 10]";
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| ValidateTimeframe - Must be one of M1, M5, M15, H1                 |
//| Req 8.7: invalid format → log error and remain in BOOT             |
//+------------------------------------------------------------------+
bool CConfigManager::ValidateTimeframe(const string tf)
{
    if(tf != "M1" && tf != "M5" && tf != "M15" && tf != "H1")
    {
        m_validationError = "Timeframe: value '" + tf +
                            "' is not valid (must be M1, M5, M15, or H1)";
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| ValidateReadTimeout - Default 10, range [1, 60]                    |
//| Req 8.7: invalid range → log error and remain in BOOT              |
//+------------------------------------------------------------------+
bool CConfigManager::ValidateReadTimeout(int value)
{
    if(value < 1 || value > 60)
    {
        m_validationError = "ReadTimeout: value " + IntegerToString(value) +
                            " is outside valid range [1, 60]";
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| GetValidationError - Returns description of what failed            |
//+------------------------------------------------------------------+
string CConfigManager::GetValidationError()
{
    return m_validationError;
}

//+------------------------------------------------------------------+
//| Accessors                                                          |
//+------------------------------------------------------------------+
string CConfigManager::GetBackendUrl()
{
    return m_backendUrl;
}

string CConfigManager::GetAuthToken()
{
    return m_authToken;
}

int CConfigManager::GetHeartbeatInterval()
{
    return m_heartbeatInterval;
}

int CConfigManager::GetHttpTimeout()
{
    return m_httpTimeout;
}

int CConfigManager::GetMaxRetries()
{
    return m_maxRetries;
}

string CConfigManager::GetTimeframe()
{
    return m_timeframe;
}

int CConfigManager::GetReadTimeout()
{
    return m_readTimeout;
}

#endif // EA_GATEWAY_CONFIG_MANAGER_MQH
