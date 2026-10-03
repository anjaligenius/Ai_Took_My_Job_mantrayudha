from dataclasses import dataclass, field
from typing import Any, List, Optional

from langchain_core.messages import AIMessage, HumanMessage


@dataclass
class ConversationMemory:
    """Cross-turn conversation state:
    - plain text message history
    - authenticated customer_id
    - remembered last_order_id
    - pending ambiguity / clarification context
    """

    turns: List[Any] = field(default_factory=list)
    customer_id: Optional[str] = None
    last_order_id: Any = None
    pending_question: Optional[str] = None

    def add_turn(self, user_message: str, reply: str) -> None:
        self.turns.append(HumanMessage(content=user_message))
        self.turns.append(AIMessage(content=reply))

    def update_context(self, trace: list, customer_id: Optional[str] = None, order_id: Optional[str] = None) -> None:
        if customer_id:
            self.customer_id = customer_id
        if order_id:
            self.last_order_id = order_id
        for entry in trace:
            args = entry.get("args") or {}
            result = entry.get("result") or {}
            oid = args.get("order_id")
            if oid is None and isinstance(result, dict):
                oid = result.get("order_id")
            if oid is not None:
                self.last_order_id = oid

    def update_last_order_id(self, trace: list, order_id: Optional[str] = None) -> None:
        self.update_context(trace, order_id=order_id)

    def context_note(self) -> str:
        if self.last_order_id is not None:
            return f"(Context: the customer was last discussing order {self.last_order_id}.)\n"
        return ""
