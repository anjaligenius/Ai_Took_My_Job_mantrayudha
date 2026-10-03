# NovaMart Refund Policy

| Field | Value |
|---|---|
| Policy | Refund Policy |
| Version | v2 |
| **Effective date** | **2026-06-01** |
| Applies to | Orders **placed** (`orders.order_date`) on or after 2026-06-01 00:00 IST |
| Supersedes | Refund Policy v1 (effective 2026-01-01) for those orders only |
| Owner | Customer Operations, NovaMart |

## 1. Purpose
Defines refund eligibility, amounts, methods and approvals for orders placed on or after 2026-06-01. Read together with Return Policy v2, Replacement Policy, Payment Policy and the Customer Escalation Policy.

## 2. Which version applies to an order
1. The version is determined by the **order placement date**. Orders placed before 2026-06-01 remain governed by Refund Policy v1, **even when the customer writes in after 2026-06-01**.
2. This policy is not applied retroactively.
3. Each order in a conversation is judged on its own placement date.

## 3. Refund eligibility and time windows
Windows are **calendar days from the delivery date** (`orders.actual_delivery_date`); delivery day is **day 0**. A request on day N is in time if N <= window.

| Reason for refund | Window under v2 | Conditions |
|---|---|---|
| Change of mind (returnable, unused, complete, original packaging) | **7 days** | `products.returnable = true`. Loyalty extension may apply (section 7). Restocking fee may apply (section 4). |
| Product defective / dead on arrival | **10 days** | Photo/video evidence; item returned for QC. |
| Product damaged in transit | **10 days** | Photos of the item **and** outer packaging. |
| Wrong item delivered | **10 days** | Photos of item and label; original item returned. |
| Item missing from the package | **10 days** | Photo of package as received; refund limited to the missing item. |
| Order not delivered / lost | Claim allowed from ETA + 7 days until 30 days after `estimated_delivery_date` | Only when delivery status is not "delivered". |
| Order cancelled before shipment (prepaid) | Automatic | See Cancellation Policy. |
| Duplicate or excess charge | 30 days from charge date | Verified with payment records. |

Note: the defect/damage/wrong-item window (10 days) is **longer** than the change-of-mind window (7 days). A customer who is outside the change-of-mind window may still be inside the defect window. Beyond the defect window, a faulty product is handled under the **Warranty Policy**, not as a refund.

## 4. Refund amount
1. **Items:** refund = `order_items.final_price` (net of discounts) **plus 18% GST on that item**.
2. **Shipping fee** is refunded only for (a) full-order cancellation before shipment, (b) full-order return due to a wrong/damaged/defective item, (c) lost orders. Partial returns never refund shipping.
3. **Cap:** never more than the amount paid for the item(s); total refunds on an order never exceed `orders.total_amount`. Requests for "compensation" or amounts above the order value are declined; state the maximum refundable amount.
4. **Restocking fee (new in v2):** change-of-mind returns of **Laptops, Tablets, Cameras and Monitors** carry a restocking fee of **5% of the item refund, capped at INR 2,500**, deducted from the refund. No fee applies to defective, damaged or wrong-item returns, or to other categories.
5. Coupons: refund is net of discounts applied.

## 5. Refund method and timelines
- **Original payment method only.** Cash-on-delivery refunds go to the NovaMart wallet (instant) or a verified bank account (see Payment Policy).
- Released **within 3 business days after the returned item passes QC**.
- Wallet - instant; UPI - 1-3 business days; cards and net banking - 5-7 business days.

## 6. Approval requirements
| Situation | Who can approve |
|---|---|
| Order total (`orders.total_amount`) of **INR 75,000 or less** and all conditions met | Tier 1 agent / AI agent may initiate |
| Order total **above INR 75,000** (lowered from INR 1,00,000 in v1) | **Human approval** by a Refund Approver is mandatory before any refund is released |
| Account status `suspended` | Human review (Trust & Safety) |
| Refund destination other than the original payment method | Not permitted; escalate to Payments if the original instrument is unavailable |
| Pattern of repeated claims (see Customer Escalation Policy) | Human review |

The threshold is evaluated on the **order total**, not the value of the returned item. A return of a INR 600 accessory from a INR 90,000 order therefore needs approval.

## 7. Exceptions (legitimate)
1. **Loyalty extension (change of mind only):** Gold +2 days, Platinum +3 days.
2. **Request raised in time:** if the customer raised a return/refund/damage request inside the window and the return could not be completed because of NovaMart or courier delay, eligibility is judged on the original request date (`support_tickets.created_at`).
3. **Goodwill credit:** up to INR 300 wallet credit by a Tier 1 agent for severe delays (see Shipping Policy). Not a refund.
4. Any other exception needs a Support Lead.

## 8. Not refundable
Items with `returnable = false` (for change of mind), items returned used/damaged/incomplete, gift cards, accounts under investigation.

## 9. Escalate to a human when
- the order total exceeds INR 75,000 and a refund is requested;
- the account is suspended, or a different refund destination is requested;
- delivery is marked delivered with OTP verified and the customer disputes it;
- customer statements are contradictory or conflict with the order record;
- legal threat or product safety issue.

## 10. Worked examples
- Order placed 2026-07-01, delivered 2026-07-06, change-of-mind request 2026-07-14 (day 8): **not eligible** (7-day window) - the same day count would have been in time under v1.
- Same order, report of a dead unit on 2026-07-14 (day 8): **eligible** (10-day defect window).
- Laptop, change of mind, refund before fee INR 47,200: fee = 5% = INR 2,360, refund INR 44,840.
- Order total INR 85,000 (placed under v2), valid return: human approval required. Under v1 the same order would not have needed approval.
