//+------------------------------------------------------------------+
//|                                                 StateMachine.mqh   |
//|                         EA Gateway - Finite State Machine           |
//|                         FSM transitions and validation              |
//+------------------------------------------------------------------+
#ifndef EA_GATEWAY_STATEMACHINE_MQH
#define EA_GATEWAY_STATEMACHINE_MQH

#include "Types.mqh"
#include "Logger.mqh"

//+------------------------------------------------------------------+
//| Total number of EA states                                          |
//+------------------------------------------------------------------+
#define EA_STATE_COUNT 10

//+------------------------------------------------------------------+
//| CStateMachine - FSM with transition validation and logging         |
//+------------------------------------------------------------------+
class CStateMachine
{
private:
    EAState   m_currentState;                          // Current FSM state
    CLogger  *m_logger;                                // Logger reference
    bool      m_transitionTable[EA_STATE_COUNT][EA_STATE_COUNT]; // Valid transitions matrix

    //--- Private helpers
    void      InitTransitionTable();
    int       StateToIndex(EAState state);

public:
    //--- Constructor / Destructor
              CStateMachine(CLogger *logger);
             ~CStateMachine();

    //--- Core FSM interface
    EAState   GetCurrentState();
    bool      TransitionTo(EAState newState, string reason);
    bool      IsValidTransition(EAState from, EAState to);

    //--- Conversion utilities
    string    StateToString(EAState state);
    EAState   StringToState(string stateStr);
};

//+------------------------------------------------------------------+
//| Constructor - Initialize state to BOOT, build transition table     |
//+------------------------------------------------------------------+
CStateMachine::CStateMachine(CLogger *logger)
{
    m_currentState = STATE_BOOT;
    m_logger       = logger;

    InitTransitionTable();

    if(m_logger != NULL)
        m_logger->Info("StateMachine", "State machine initialized in BOOT state");
}

//+------------------------------------------------------------------+
//| Destructor                                                         |
//+------------------------------------------------------------------+
CStateMachine::~CStateMachine()
{
    // Logger is externally owned, do not delete
}

//+------------------------------------------------------------------+
//| InitTransitionTable - Populate the 2D boolean transition matrix     |
//|                                                                    |
//| Valid transitions from the design:                                  |
//|   BOOT → CONNECT                                                   |
//|   CONNECT → WAIT_SESSION                                           |
//|   CONNECT → DISCONNECTED                                           |
//|   WAIT_SESSION → CHECK_RISK                                        |
//|   CHECK_RISK → SCAN_SIGNAL                                         |
//|   CHECK_RISK → WAIT_SESSION                                        |
//|   SCAN_SIGNAL → AI_CONFIRMATION                                    |
//|   SCAN_SIGNAL → WAIT_SESSION                                       |
//|   AI_CONFIRMATION → OPEN_POSITION                                  |
//|   AI_CONFIRMATION → WAIT_SESSION                                   |
//|   OPEN_POSITION → MANAGE_POSITION                                  |
//|   MANAGE_POSITION → POSITION_CLOSED                                |
//|   POSITION_CLOSED → WAIT_SESSION                                   |
//|   ANY → DISCONNECTED                                               |
//|   DISCONNECTED → WAIT_SESSION                                      |
//+------------------------------------------------------------------+
void CStateMachine::InitTransitionTable()
{
    // Initialize all transitions to false
    for(int i = 0; i < EA_STATE_COUNT; i++)
        for(int j = 0; j < EA_STATE_COUNT; j++)
            m_transitionTable[i][j] = false;

    // BOOT → CONNECT
    m_transitionTable[StateToIndex(STATE_BOOT)][StateToIndex(STATE_CONNECT)] = true;

    // CONNECT → WAIT_SESSION
    m_transitionTable[StateToIndex(STATE_CONNECT)][StateToIndex(STATE_WAIT_SESSION)] = true;

    // CONNECT → DISCONNECTED
    m_transitionTable[StateToIndex(STATE_CONNECT)][StateToIndex(STATE_DISCONNECTED)] = true;

    // WAIT_SESSION → CHECK_RISK
    m_transitionTable[StateToIndex(STATE_WAIT_SESSION)][StateToIndex(STATE_CHECK_RISK)] = true;

    // CHECK_RISK → SCAN_SIGNAL
    m_transitionTable[StateToIndex(STATE_CHECK_RISK)][StateToIndex(STATE_SCAN_SIGNAL)] = true;

    // CHECK_RISK → WAIT_SESSION
    m_transitionTable[StateToIndex(STATE_CHECK_RISK)][StateToIndex(STATE_WAIT_SESSION)] = true;

    // SCAN_SIGNAL → AI_CONFIRMATION
    m_transitionTable[StateToIndex(STATE_SCAN_SIGNAL)][StateToIndex(STATE_AI_CONFIRMATION)] = true;

    // SCAN_SIGNAL → WAIT_SESSION
    m_transitionTable[StateToIndex(STATE_SCAN_SIGNAL)][StateToIndex(STATE_WAIT_SESSION)] = true;

    // AI_CONFIRMATION → OPEN_POSITION
    m_transitionTable[StateToIndex(STATE_AI_CONFIRMATION)][StateToIndex(STATE_OPEN_POSITION)] = true;

    // AI_CONFIRMATION → WAIT_SESSION
    m_transitionTable[StateToIndex(STATE_AI_CONFIRMATION)][StateToIndex(STATE_WAIT_SESSION)] = true;

    // OPEN_POSITION → MANAGE_POSITION
    m_transitionTable[StateToIndex(STATE_OPEN_POSITION)][StateToIndex(STATE_MANAGE_POSITION)] = true;

    // MANAGE_POSITION → POSITION_CLOSED
    m_transitionTable[StateToIndex(STATE_MANAGE_POSITION)][StateToIndex(STATE_POSITION_CLOSED)] = true;

    // POSITION_CLOSED → WAIT_SESSION
    m_transitionTable[StateToIndex(STATE_POSITION_CLOSED)][StateToIndex(STATE_WAIT_SESSION)] = true;

    // ANY → DISCONNECTED (every state can transition to DISCONNECTED)
    for(int i = 0; i < EA_STATE_COUNT; i++)
        m_transitionTable[i][StateToIndex(STATE_DISCONNECTED)] = true;

    // Prevent DISCONNECTED → DISCONNECTED (self-transition not meaningful)
    m_transitionTable[StateToIndex(STATE_DISCONNECTED)][StateToIndex(STATE_DISCONNECTED)] = false;

    // DISCONNECTED → WAIT_SESSION
    m_transitionTable[StateToIndex(STATE_DISCONNECTED)][StateToIndex(STATE_WAIT_SESSION)] = true;
}

//+------------------------------------------------------------------+
//| StateToIndex - Map EAState enum value to array index               |
//+------------------------------------------------------------------+
int CStateMachine::StateToIndex(EAState state)
{
    switch(state)
    {
        case STATE_BOOT:              return 0;
        case STATE_CONNECT:           return 1;
        case STATE_WAIT_SESSION:      return 2;
        case STATE_CHECK_RISK:        return 3;
        case STATE_SCAN_SIGNAL:       return 4;
        case STATE_AI_CONFIRMATION:   return 5;
        case STATE_OPEN_POSITION:     return 6;
        case STATE_MANAGE_POSITION:   return 7;
        case STATE_POSITION_CLOSED:   return 8;
        case STATE_DISCONNECTED:      return 9;
        default:                      return 0;
    }
}

//+------------------------------------------------------------------+
//| GetCurrentState - Return current FSM state                         |
//+------------------------------------------------------------------+
EAState CStateMachine::GetCurrentState()
{
    return m_currentState;
}

//+------------------------------------------------------------------+
//| IsValidTransition - Check if transition from→to is allowed         |
//+------------------------------------------------------------------+
bool CStateMachine::IsValidTransition(EAState from, EAState to)
{
    int fromIdx = StateToIndex(from);
    int toIdx   = StateToIndex(to);

    // Bounds check
    if(fromIdx < 0 || fromIdx >= EA_STATE_COUNT ||
       toIdx < 0   || toIdx >= EA_STATE_COUNT)
        return false;

    return m_transitionTable[fromIdx][toIdx];
}

//+------------------------------------------------------------------+
//| TransitionTo - Attempt a state transition with validation          |
//| Returns true if transition succeeded, false if rejected            |
//+------------------------------------------------------------------+
bool CStateMachine::TransitionTo(EAState newState, string reason)
{
    // Check if transition is valid
    if(!IsValidTransition(m_currentState, newState))
    {
        // Invalid transition - log warning, remain in current state
        if(m_logger != NULL)
        {
            string msg = "Invalid transition rejected: " +
                         StateToString(m_currentState) + " → " +
                         StateToString(newState) +
                         " (reason: " + reason + ")";
            m_logger->Warn("StateMachine", msg);
        }
        return false;
    }

    // Valid transition - perform it
    EAState previousState = m_currentState;
    m_currentState = newState;

    // Log the successful transition
    if(m_logger != NULL)
    {
        m_logger->LogStateTransition(previousState, newState, reason);
        m_logger->SetCurrentState(newState);
    }

    return true;
}

//+------------------------------------------------------------------+
//| StateToString - Convert EAState enum to readable string            |
//+------------------------------------------------------------------+
string CStateMachine::StateToString(EAState state)
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
//| StringToState - Convert string to EAState enum                     |
//| Returns STATE_BOOT as default for unrecognized strings             |
//+------------------------------------------------------------------+
EAState CStateMachine::StringToState(string stateStr)
{
    if(stateStr == "BOOT")              return STATE_BOOT;
    if(stateStr == "CONNECT")           return STATE_CONNECT;
    if(stateStr == "WAIT_SESSION")      return STATE_WAIT_SESSION;
    if(stateStr == "CHECK_RISK")        return STATE_CHECK_RISK;
    if(stateStr == "SCAN_SIGNAL")       return STATE_SCAN_SIGNAL;
    if(stateStr == "AI_CONFIRMATION")   return STATE_AI_CONFIRMATION;
    if(stateStr == "OPEN_POSITION")     return STATE_OPEN_POSITION;
    if(stateStr == "MANAGE_POSITION")   return STATE_MANAGE_POSITION;
    if(stateStr == "POSITION_CLOSED")   return STATE_POSITION_CLOSED;
    if(stateStr == "DISCONNECTED")      return STATE_DISCONNECTED;

    // Unrecognized string - return BOOT as safe default
    if(m_logger != NULL)
        m_logger->Warn("StateMachine", "Unrecognized state string: " + stateStr + ", defaulting to BOOT");

    return STATE_BOOT;
}

#endif // EA_GATEWAY_STATEMACHINE_MQH
