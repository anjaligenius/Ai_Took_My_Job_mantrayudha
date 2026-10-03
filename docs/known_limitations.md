# MANTRAYUDHA AI Customer Support Agent — Known Limitations & Boundaries

## 1. Scope & System Boundaries
This document formalizes the operational boundaries, policy constraints, and intentional constraints implemented within the NovaMart AI Customer Support Agent.

---

## 2. Documented Edge Cases & Constraints

### 2.1 Shipping Address Modifications
- **Dispatched & Delivered Orders**: Per NovaMart policy, shipping addresses cannot be modified on orders that have already reached `shipped`, `out_for_delivery`, or `delivered` status. The agent refuses the modification and guides the customer to update their default address in Account Settings.
- **Pre-Dispatch Orders**: For orders in `placed`, `confirmed`, or `processing` status, address updates are accepted and flagged for support desk modification prior to courier handover.

### 2.2 Delivery Disputes on OTP-Verified Deliveries
- When a customer claims an order was never received, but the database records show `delivery_status == 'delivered'` with `delivery_otp_verified == True`:
  - The agent **never** issues an instant refund.
  - The agent flags a `contradictory_otp_claim` risk signal.
  - The case is escalated to the **Logistics Desk** with a newly generated support ticket for courier investigation.
  - If a refund was requested in the same query, it is explicitly held pending resolution.

### 2.3 Excess Refund Demands
- When a customer demands an arbitrary refund amount exceeding the order value (e.g. ₹50,000 for a ₹2,499 order):
  - Per Handbook Page 11, the agent does **not** escalate solely due to excess claim.
  - The agent caps the allowable refund to $\min(\text{requested}, \text{order\_total} - \text{restocking\_fee})$.
  - The excess is refused, and the customer is offered the legally permissible amount.

### 2.4 High-Value Human Approval Thresholds
- Under **Policy v1** (orders before June 1, 2026), orders exceeding ₹100,000 require human authorization.
- Under **Policy v2** (orders on/after June 1, 2026), the threshold is lowered to ₹75,000.
- When an order exceeds the threshold, the agent cannot execute `ACT`; it escalates to `Refunds & Payments` with an escalation ticket.

### 2.5 Category Returnability & Restocking Fees
- Certain hygienic categories (e.g. innerwear, beauty items) are non-returnable for change-of-mind reasons.
- Under **Policy v2**, select electronics and large appliances incur a 5% restocking fee (capped at ₹1,500) upon return for change of mind. Defective items are exempt from restocking fees.

### 2.6 Multi-Turn Disambiguation & Continuity
- When a user has multiple active orders and asks an ambiguous question ("I want to return my order"), the agent asks (`ASK`) to specify the order ID.
- In subsequent turns, when the customer provides just an order number (e.g. `ORD-005144`), the agent retains the intent from previous turns and resumes the evaluation loop without treating it as an unrecognized intent.

---

## 3. Operational Assumptions
1. **Authoritative Truth**: The SQLite database (`support_agent.db`) is the absolute ground truth. LLM generation cannot override database records.
2. **Deterministic Pricing**: Tax amounts (18% GST) and restocking fees are computed using fixed decimal arithmetic rather than LLM text generation.
3. **Idempotency**: All mutations (`cancel_order`, `create_refund`, `create_return`) use idempotency keys to prevent duplicate chargebacks or double-cancellations.
