//+------------------------------------------------------------------+
//|                                                      Inputs.mqh   |
//|                         EA Gateway - Input Parameters              |
//|                         Configurable settings via MT5 UI           |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_INPUTS_MQH
#define EA_GATEWAY_INPUTS_MQH

//+------------------------------------------------------------------+
//| Input Parameters                                                   |
//| These appear in the MT5 EA Properties dialog for user config       |
//+------------------------------------------------------------------+

input string InpBackendUrl      = "https://api.example.com";  // Backend URL (max 2048 chars)
input string InpAuthToken       = "";                          // Auth token (max 512 chars)
input int    InpHeartbeatSec    = 30;                          // Heartbeat interval [5-300] seconds
input int    InpHttpTimeoutSec  = 5;                           // HTTP connect timeout [1-60] seconds
input int    InpMaxRetries      = 3;                           // Max retries on 5xx [0-10]
input string InpTimeframe       = "M1";                        // Timeframe (M1, M5, M15, H1)
input int    InpReadTimeoutSec  = 10;                          // HTTP read timeout [1-60] seconds

#endif // EA_GATEWAY_INPUTS_MQH
