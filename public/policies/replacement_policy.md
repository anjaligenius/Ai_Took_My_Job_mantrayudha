# NovaMart Replacement Policy

| Field | Value |
|---|---|
| Policy | Replacement Policy |
| Version | 1.0 (single version; windows come from the Refund Policy version of the order) |
| **Effective date** | **2026-01-01** |
| Applies to | All orders |

## 1. When a replacement is offered
- Product dead on arrival / defective, damaged in transit, or wrong item delivered,
- reported **inside the defect window** of the Refund Policy that applies to the order (v1: 15 days, v2: 10 days after delivery),
- with **photo/video evidence** (product, serial/label and outer packaging),
- and the product has `products.replacement_available = true`.

Change-of-mind is **not** a replacement reason.

## 2. When a replacement is not offered
| Situation | Remedy |
|---|---|
| `replacement_available = false` | Refund (initiate a return for refund), not a replacement |
| Product out of stock / discontinued | Offer refund, or ask whether the customer wants to wait for restock |
| Reported after the defect window | Warranty service (Warranty Policy) |
| No evidence provided | **Ask for evidence first**; take no action until received |
| Customer already received a replacement for this order item | Escalate (one replacement per order item) |

## 3. Process
1. Verify order, delivery date, product, evidence.
2. Create the replacement request; the faulty/wrong unit is collected at the time the new unit is delivered (pickup within 48 hours).
3. Replacement ships within 2 business days of pickup QC; free shipping.
4. If QC finds the claim invalid the replacement is cancelled and the customer informed.

## 4. Approval
- Orders with `total_amount` above the approval threshold of the applicable Refund Policy (v1: INR 1,00,000; v2: INR 75,000) need **human approval** before a replacement or refund is released. This includes wrong-item cases on expensive orders.
- Otherwise the agent may create the request directly.

## 5. Customer choice
For defective/damaged/wrong items the customer may choose a refund instead of a replacement. Refund rules follow the Refund Policy.

## 6. Replacements and warranty
A replacement under this policy starts a fresh warranty period of the product's `warranty_months` from the replacement's delivery.
