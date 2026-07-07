//+------------------------------------------------------------------+
//|                                                  HttpClient.mqh   |
//|                         EA Gateway - HTTP Communication            |
//|                         Retry logic, timeout, and auth handling    |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_HTTPCLIENT_MQH
#define EA_GATEWAY_HTTPCLIENT_MQH

#include "Types.mqh"
#include "Logger.mqh"

//+------------------------------------------------------------------+
//| Constants                                                          |
//+------------------------------------------------------------------+
#define HTTP_MAX_PAYLOAD_BYTES  1048576   // 1MB payload size limit
#define HTTP_STATUS_TIMEOUT    -1        // WebRequest returns -1 on error
#define HTTP_BACKOFF_BASE_MS   1000      // Base backoff: 1 second
#define HTTP_RECONNECT_FAILURES 10       // Consecutive failures for disconnect

//+------------------------------------------------------------------+
//| CHttpClient - HTTP communication with retry and timeout logic      |
//+------------------------------------------------------------------+
class CHttpClient
{
private:
    string    m_baseUrl;              // Base URL for all requests
    string    m_authToken;            // Authentication token
    int       m_connectTimeoutMs;     // Connect timeout in milliseconds
    int       m_readTimeoutMs;        // Read timeout in milliseconds
    int       m_maxRetries;           // Maximum retry attempts on 5xx
    int       m_lastLatencyMs;        // Last measured request latency
    int       m_consecutiveFailures;  // Consecutive connection failures
    bool      m_isConnected;          // Connection status flag
    CLogger*  m_logger;              // Pointer to logger instance

    //--- Private helpers
    bool      ShouldRetry(int statusCode, int attempt);
    int       GetBackoffMs(int attempt);
    bool      IsValidJson(const string &body);
    string    BuildHeaders();
    int       GetTimeoutMs();

public:
    //--- Constructor / Destructor
              CHttpClient();
             ~CHttpClient();

    //--- Configuration
    void      Init(CLogger* logger);
    void      SetBaseUrl(string url);
    void      SetAuthToken(string token);
    void      SetTimeout(int connectTimeoutSec, int readTimeoutSec);
    void      SetMaxRetries(int retries);

    //--- Core communication
    HttpResponse Post(string endpoint, string jsonPayload);

    //--- Status accessors
    bool      IsConnected();
    int       GetLastLatencyMs();
    int       GetConsecutiveFailures();
    void      ResetConsecutiveFailures();
};

//+------------------------------------------------------------------+
//| Constructor                                                        |
//+------------------------------------------------------------------+
CHttpClient::CHttpClient()
{
    m_baseUrl             = "";
    m_authToken           = "";
    m_connectTimeoutMs    = 5000;   // Default 5 seconds
    m_readTimeoutMs       = 10000;  // Default 10 seconds
    m_maxRetries          = 3;
    m_lastLatencyMs       = 0;
    m_consecutiveFailures = 0;
    m_isConnected         = false;
    m_logger              = NULL;
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CHttpClient::~CHttpClient()
{
    // Logger is not owned by HttpClient, do not delete
    m_logger = NULL;
}

//+------------------------------------------------------------------+
//| Init - Set logger reference                                        |
//+------------------------------------------------------------------+
void CHttpClient::Init(CLogger* logger)
{
    m_logger = logger;
}

//+------------------------------------------------------------------+
//| SetBaseUrl - Configure base URL for all requests                   |
//+------------------------------------------------------------------+
void CHttpClient::SetBaseUrl(string url)
{
    m_baseUrl = url;
    // Remove trailing slash if present
    if(StringLen(m_baseUrl) > 0 && StringSubstr(m_baseUrl, StringLen(m_baseUrl) - 1, 1) == "/")
        m_baseUrl = StringSubstr(m_baseUrl, 0, StringLen(m_baseUrl) - 1);
}

//+------------------------------------------------------------------+
//| SetAuthToken - Configure authentication token                      |
//+------------------------------------------------------------------+
void CHttpClient::SetAuthToken(string token)
{
    m_authToken = token;
}

//+------------------------------------------------------------------+
//| SetTimeout - Configure connect and read timeouts                   |
//+------------------------------------------------------------------+
void CHttpClient::SetTimeout(int connectTimeoutSec, int readTimeoutSec)
{
    m_connectTimeoutMs = connectTimeoutSec * 1000;
    m_readTimeoutMs    = readTimeoutSec * 1000;
}

//+------------------------------------------------------------------+
//| SetMaxRetries - Configure maximum retry count for 5xx errors       |
//+------------------------------------------------------------------+
void CHttpClient::SetMaxRetries(int retries)
{
    m_maxRetries = retries;
}

//+------------------------------------------------------------------+
//| GetTimeoutMs - Get the effective timeout for WebRequest            |
//| WebRequest uses a single timeout value; use the larger of the two  |
//+------------------------------------------------------------------+
int CHttpClient::GetTimeoutMs()
{
    // WebRequest has a single timeout parameter that covers the full
    // request lifecycle. We use connectTimeout + readTimeout as the
    // total allowed time for the request.
    return m_connectTimeoutMs + m_readTimeoutMs;
}

//+------------------------------------------------------------------+
//| BuildHeaders - Construct HTTP headers with auth and content type   |
//+------------------------------------------------------------------+
string CHttpClient::BuildHeaders()
{
    string headers = "Content-Type: application/json\r\n";
    headers += "X-Auth-Token: " + m_authToken + "\r\n";
    return headers;
}

//+------------------------------------------------------------------+
//| IsValidJson - Basic JSON validity check                            |
//| Returns true if body starts with '{' or '[' (basic heuristic)      |
//+------------------------------------------------------------------+
bool CHttpClient::IsValidJson(const string &body)
{
    if(StringLen(body) == 0)
        return false;

    string trimmed = body;
    StringTrimLeft(trimmed);

    if(StringLen(trimmed) == 0)
        return false;

    string firstChar = StringSubstr(trimmed, 0, 1);
    return (firstChar == "{" || firstChar == "[");
}

//+------------------------------------------------------------------+
//| ShouldRetry - Determine if request should be retried               |
//| Only 5xx responses are retried, up to MaxRetries times             |
//+------------------------------------------------------------------+
bool CHttpClient::ShouldRetry(int statusCode, int attempt)
{
    // Only retry on 5xx server errors
    if(statusCode >= 500 && statusCode < 600)
    {
        return (attempt < m_maxRetries);
    }
    return false;
}

//+------------------------------------------------------------------+
//| GetBackoffMs - Calculate exponential backoff delay                  |
//| Pattern: 1000ms, 2000ms, 4000ms (1s * 2^attempt)                  |
//+------------------------------------------------------------------+
int CHttpClient::GetBackoffMs(int attempt)
{
    // attempt 0 → 1000ms, attempt 1 → 2000ms, attempt 2 → 4000ms
    int backoff = HTTP_BACKOFF_BASE_MS;
    for(int i = 0; i < attempt; i++)
        backoff *= 2;
    return backoff;
}

//+------------------------------------------------------------------+
//| Post - Send HTTP POST request with full retry and error handling   |
//|                                                                    |
//| Returns HttpResponse with:                                         |
//|   statusCode: HTTP status or -1 for connection failure             |
//|   body: response body string                                       |
//|   latencyMs: round-trip time in milliseconds                       |
//|   isValid: true if response body is parseable JSON                 |
//+------------------------------------------------------------------+
HttpResponse CHttpClient::Post(string endpoint, string jsonPayload)
{
    HttpResponse response;
    response.statusCode = 0;
    response.body       = "";
    response.latencyMs  = 0;
    response.isValid    = false;

    //--- Enforce payload size limit (1MB)
    if(StringLen(jsonPayload) > HTTP_MAX_PAYLOAD_BYTES)
    {
        if(m_logger != NULL)
            m_logger.Error("HttpClient", "Payload size exceeds 1MB limit. Size: " +
                          IntegerToString(StringLen(jsonPayload)) + " bytes. Endpoint: " + endpoint);
        response.statusCode = 0;
        response.isValid    = false;
        return response;
    }

    //--- Build full URL
    string fullUrl = m_baseUrl + endpoint;

    //--- Build headers with auth token
    string headers = BuildHeaders();

    //--- Convert payload to char array for WebRequest
    char postData[];
    char resultData[];
    string resultHeaders = "";

    StringToCharArray(jsonPayload, postData, 0, WHOLE_ARRAY, CP_UTF8);
    // Remove null terminator that StringToCharArray adds
    if(ArraySize(postData) > 0 && postData[ArraySize(postData) - 1] == 0)
        ArrayResize(postData, ArraySize(postData) - 1);

    //--- Get timeout value
    int timeoutMs = GetTimeoutMs();

    //--- Retry loop
    int attempt = 0;
    bool requestComplete = false;

    while(!requestComplete)
    {
        //--- Measure latency
        uint startTime = GetTickCount();

        //--- Execute WebRequest
        int statusCode = WebRequest(
            "POST",
            fullUrl,
            headers,
            timeoutMs,
            postData,
            resultData,
            resultHeaders
        );

        //--- Calculate latency
        uint endTime = GetTickCount();
        int latency = (int)(endTime - startTime);
        m_lastLatencyMs = latency;
        response.latencyMs = latency;

        //--- Handle connection timeout / error (WebRequest returns -1)
        if(statusCode == HTTP_STATUS_TIMEOUT)
        {
            m_consecutiveFailures++;

            if(m_logger != NULL)
                m_logger.Error("HttpClient", "Connection timeout/error after " +
                              IntegerToString(latency) + "ms to " + endpoint +
                              ". Consecutive failures: " + IntegerToString(m_consecutiveFailures) +
                              ". LastError: " + IntegerToString(GetLastError()));

            // Signal reconnection needed
            m_isConnected = false;
            response.statusCode = -1;
            response.body       = "";
            response.isValid    = false;
            return response;
        }

        //--- Connection successful, reset or track failures
        response.statusCode = statusCode;

        //--- Convert result to string
        if(ArraySize(resultData) > 0)
            response.body = CharArrayToString(resultData, 0, WHOLE_ARRAY, CP_UTF8);
        else
            response.body = "";

        //--- Handle 2xx success
        if(statusCode >= 200 && statusCode < 300)
        {
            // Reset consecutive failures on success
            m_consecutiveFailures = 0;
            m_isConnected = true;

            // Check if response is valid JSON
            response.isValid = IsValidJson(response.body);

            if(!response.isValid && StringLen(response.body) > 0)
            {
                if(m_logger != NULL)
                    m_logger.Warn("HttpClient", "Invalid JSON response from " + endpoint +
                                 ". Status: " + IntegerToString(statusCode) +
                                 ". Body (first 200 chars): " +
                                 StringSubstr(response.body, 0, 200));
            }

            requestComplete = true;
        }
        //--- Handle 4xx client error (no retry)
        else if(statusCode >= 400 && statusCode < 500)
        {
            // Reset consecutive failures (server is reachable)
            m_consecutiveFailures = 0;
            m_isConnected = true;

            if(m_logger != NULL)
                m_logger.Error("HttpClient", "Client error " + IntegerToString(statusCode) +
                              " from " + endpoint + ". Body: " +
                              StringSubstr(response.body, 0, 500));

            // Check JSON validity of error response
            response.isValid = IsValidJson(response.body);
            requestComplete = true;
        }
        //--- Handle 5xx server error (retry with backoff)
        else if(statusCode >= 500 && statusCode < 600)
        {
            if(ShouldRetry(statusCode, attempt))
            {
                int backoffMs = GetBackoffMs(attempt);

                if(m_logger != NULL)
                    m_logger.Warn("HttpClient", "Server error " + IntegerToString(statusCode) +
                                 " from " + endpoint + ". Retry " +
                                 IntegerToString(attempt + 1) + "/" + IntegerToString(m_maxRetries) +
                                 " after " + IntegerToString(backoffMs) + "ms");

                // Wait with exponential backoff
                Sleep(backoffMs);
                attempt++;
            }
            else
            {
                // All retries exhausted
                m_consecutiveFailures++;

                if(m_logger != NULL)
                    m_logger.Error("HttpClient", "All " + IntegerToString(m_maxRetries) +
                                  " retries exhausted for " + endpoint +
                                  ". Last status: " + IntegerToString(statusCode) +
                                  ". Consecutive failures: " + IntegerToString(m_consecutiveFailures));

                response.isValid = IsValidJson(response.body);
                requestComplete = true;
            }
        }
        //--- Handle unexpected status codes
        else
        {
            m_consecutiveFailures = 0;
            m_isConnected = true;

            if(m_logger != NULL)
                m_logger.Warn("HttpClient", "Unexpected status " + IntegerToString(statusCode) +
                             " from " + endpoint);

            response.isValid = IsValidJson(response.body);
            requestComplete = true;
        }
    }

    return response;
}

//+------------------------------------------------------------------+
//| IsConnected - Check if the client is connected to the backend      |
//+------------------------------------------------------------------+
bool CHttpClient::IsConnected()
{
    return m_isConnected;
}

//+------------------------------------------------------------------+
//| GetLastLatencyMs - Get the latency of the last request             |
//+------------------------------------------------------------------+
int CHttpClient::GetLastLatencyMs()
{
    return m_lastLatencyMs;
}

//+------------------------------------------------------------------+
//| GetConsecutiveFailures - Get consecutive failure count              |
//+------------------------------------------------------------------+
int CHttpClient::GetConsecutiveFailures()
{
    return m_consecutiveFailures;
}

//+------------------------------------------------------------------+
//| ResetConsecutiveFailures - Reset failure counter (e.g., on reconnect)|
//+------------------------------------------------------------------+
void CHttpClient::ResetConsecutiveFailures()
{
    m_consecutiveFailures = 0;
    m_isConnected = true;
}

#endif // EA_GATEWAY_HTTPCLIENT_MQH
