//+------------------------------------------------------------------+
//|                                          SessionAbortHandler.mqh  |
//|                         EA Gateway - Session End Abort Logic       |
//|                         Aborts operations when session ends        |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_SESSION_ABORT_HANDLER_MQH
#define EA_GATEWAY_SESSION_ABORT_HANDLER_MQH

#include "Types.mqh"
#include "StateMachine.mqh"
#include "SessionManager.mqh"
#include "TradeExecutor.mqh"
#include "Logger.mqh"

//+------------------------------------------------------------------+
//| CSessionAbortHandler - Handles session-end abort logic             |
//|                                                                    |
//| Requirements:                                                      |
//|   4.15: IF Session_Window ends while EA is in CHECK_RISK,          |
//|         SCAN_SIGNAL, or AI_CONFIRMATION with no open position,     |
//|         THEN abort and transition back to WAIT_SESSION              |
//|   6.4:  WHEN session ends and position is still open, continue     |
//|         managing until closed by backend or SL/TP                  |
//|                                                                    |
//| Usage: Call CheckSessionAbort() on every tick or timer event.      |
//|        Returns true if an abort was triggered.                     |
//+------------------------------------------------------------------+
class CSessionAbortHandler
{
private:
    CStateMachine*    m_stateMachine;    // Pointer to FSM
    CSessionManager*  m_sessionManager;  // Pointer to session manager
    CTradeExecutor*   m_tradeExecutor;   // Pointer to trade executor
    CLogger*          m_logger;          // Pointer to logger

    //--- Helper: Check if current state is abortable
    bool              IsAbortableState(EAState state);

public:
    //--- Constructor / Destructor
                      CSessionAbortHandler();
                     ~CSessionAbortHandler();

    //--- Initialization
    void              Init(CStateMachine* stateMachine,
                           CSessionManager* sessionManager,
                           CTradeExecutor* tradeExecutor,
                           CLogger* logger);

    //--- Core method: Check and perform session abort
    bool              CheckSessionAbort();
};

//+------------------------------------------------------------------+
//| Constructor                                                        |
//+------------------------------------------------------------------+
CSessionAbortHandler::CSessionAbortHandler()
{
    m_stateMachine  = NULL;
    m_sessionManager = NULL;
    m_tradeExecutor = NULL;
    m_logger        = NULL;
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CSessionAbortHandler::~CSessionAbortHandler()
{
    // All pointers are externally owned, do not delete
    m_stateMachine  = NULL;
    m_sessionManager = NULL;
    m_tradeExecutor = NULL;
    m_logger        = NULL;
}

//+------------------------------------------------------------------+
//| Init - Set references to required components                       |
//+------------------------------------------------------------------+
void CSessionAbortHandler::Init(CStateMachine* stateMachine,
                                CSessionManager* sessionManager,
                                CTradeExecutor* tradeExecutor,
                                CLogger* logger)
{
    m_stateMachine  = stateMachine;
    m_sessionManager = sessionManager;
    m_tradeExecutor = tradeExecutor;
    m_logger        = logger;

    if(m_logger != NULL)
        m_logger.Info("SessionAbortHandler", "Initialized");
}

//+------------------------------------------------------------------+
//| IsAbortableState - Returns true if the state should be aborted     |
//|                    when session ends (with no open position)        |
//+------------------------------------------------------------------+
bool CSessionAbortHandler::IsAbortableState(EAState state)
{
    return (state == STATE_CHECK_RISK ||
            state == STATE_SCAN_SIGNAL ||
            state == STATE_AI_CONFIRMATION);
}

//+------------------------------------------------------------------+
//| CheckSessionAbort - Main logic called periodically                 |
//|                                                                    |
//| Logic:                                                             |
//| 1. If session is active → no abort needed, return false            |
//| 2. If session ended:                                               |
//|    a. If state is CHECK_RISK, SCAN_SIGNAL, or AI_CONFIRMATION:     |
//|       - If no open position → transition to WAIT_SESSION           |
//|       - If position is open → do nothing (continue managing)       |
//|    b. If state is MANAGE_POSITION → do nothing (Req 6.4)           |
//|    c. Any other state → no abort needed                            |
//|                                                                    |
//| Returns: true if abort was triggered (transition performed)        |
//|          false otherwise                                           |
//+------------------------------------------------------------------+
bool CSessionAbortHandler::CheckSessionAbort()
{
    //--- Safety checks
    if(m_stateMachine == NULL || m_sessionManager == NULL || m_tradeExecutor == NULL)
    {
        if(m_logger != NULL)
            m_logger.Error("SessionAbortHandler", "CheckSessionAbort called with NULL dependencies");
        return false;
    }

    //--- If session is still active, no abort needed
    if(m_sessionManager.IsInSession())
        return false;

    //--- Session has ended - check current state
    EAState currentState = m_stateMachine.GetCurrentState();

    //--- Only abort if in an abortable state
    if(!IsAbortableState(currentState))
        return false;

    //--- If there is an open position, do NOT abort (Req 6.4)
    //--- Continue managing the position until closed
    if(m_tradeExecutor.HasOpenPosition())
    {
        if(m_logger != NULL)
            m_logger.Info("SessionAbortHandler",
                         "Session ended but position is open. Continuing management. Ticket: " +
                         IntegerToString(m_tradeExecutor.GetOpenTicket()));
        return false;
    }

    //--- No open position and session ended → abort to WAIT_SESSION
    bool transitioned = m_stateMachine.TransitionTo(STATE_WAIT_SESSION, "session_ended");

    if(transitioned)
    {
        if(m_logger != NULL)
            m_logger.Info("SessionAbortHandler",
                         "Session ended - aborting from " +
                         m_stateMachine.StateToString(currentState) +
                         " to WAIT_SESSION (no open position)");
    }
    else
    {
        if(m_logger != NULL)
            m_logger.Error("SessionAbortHandler",
                          "Failed to transition from " +
                          m_stateMachine.StateToString(currentState) +
                          " to WAIT_SESSION on session end");
    }

    return transitioned;
}

#endif // EA_GATEWAY_SESSION_ABORT_HANDLER_MQH
