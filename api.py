import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from src.logging_config import configure_logging
from src.memory import ConversationMemory
from src.orchestrator import run_orchestrator

configure_logging()
logger = logging.getLogger("support_agent.api")

app = FastAPI(
    title="NovaMart MANTRAYUDHA Support Agent API",
    description=(
        "Production-grade AI customer-support agent for NovaMart. "
        "Strictly grounds every action in authoritative database truth and versioned policy rules."
    ),
    version="2.0.0",
)

_sessions: dict[str, ConversationMemory] = {}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The customer's message")
    session_id: Optional[str] = Field(None, description="Omit to start a new conversation")
    customer_id: Optional[str] = Field(None, description="Authenticated customer ID (e.g. CUST-00001)")
    current_date: Optional[str] = Field(None, description="Simulated current date (e.g. 2026-06-15)")


class ToolCall(BaseModel):
    agent: str
    tool: str
    args: dict
    result: Any = None


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    session_id: str
    customer_id: Optional[str] = None
    response: str
    reply: str
    decision: str  # ANSWER, ASK, ACT, ESCALATE
    agent: str
    trace: List[ToolCall]
    usage: Usage
    cached: bool = False
    action_verified: bool = False


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "request",
        extra={
            "extra_fields": {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": elapsed_ms,
            }
        },
    )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or uuid.uuid4().hex
    memory = _sessions.setdefault(session_id, ConversationMemory())
    if req.customer_id:
        memory.customer_id = req.customer_id

    augmented_message = memory.context_note() + req.message
    try:
        import inspect
        sig = inspect.signature(run_orchestrator)
        kwargs = {"history": memory.turns}
        if "customer_id" in sig.parameters:
            kwargs["customer_id"] = memory.customer_id or req.customer_id
        if "session_id" in sig.parameters:
            kwargs["session_id"] = session_id
        if "current_date" in sig.parameters:
            kwargs["current_date"] = req.current_date

        result = run_orchestrator(augmented_message, **kwargs)
    except TypeError:
        # Fallback if monkeypatched without extra kwargs
        result = run_orchestrator(augmented_message, history=memory.turns)
    except Exception as exc:
        logger.exception("Orchestrator unhandled error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    reply = result.get("reply", "")
    decision = result.get("decision", "ANSWER")
    trace = result.get("trace", [])

    memory.add_turn(req.message, reply)
    memory.update_last_order_id(trace)

    return ChatResponse(
        session_id=session_id,
        customer_id=memory.customer_id,
        response=reply,
        reply=reply,
        decision=decision,
        agent=result.get("agent", "support"),
        trace=trace,
        usage=Usage(**(result.get("usage") or {})),
        cached=result.get("cached", False),
        action_verified=result.get("action_verified", False),
    )
