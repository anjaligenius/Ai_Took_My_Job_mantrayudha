# NovaMart Refund Policy

| Field | Value |
|---|---|
| Policy | Refund Policy |
| Version | v1 |
| **Effective date** | **2026-01-01** |
| Applies to | Orders **placed** (`orders.order_date`) from 2026-01-01 00:00 IST up to and including 2026-05-31 23:59 IST |
| Superseded by | Refund Policy v2 (effective 2026-06-01) - but only for orders placed on or after that date |
| Owner | Customer Operations, NovaMart |

## 1. Purpose
This document defines when NovaMart refunds a customer, how much, how, and who must approve it. It is read together with the Return Policy of the same date range, the Replacement Policy, the Payment Policy and the Customer Escalation Policy.

## 2. Which version applies to an order
1. The applicable policy version is determined by the **order placement date**, not by the delivery date, the ticket date or the date on which the customer writes in.
2. A newer version is **never applied retroactively**. An order placed on 2026-05-28 stays under v1 even if it is delivered, returned or complained about after 2026-06-01.
3. Where a customer has several orders, each order is judged under its own version.

## 3. Refund eligibility and time windows
All windows are counted in **calendar days from the delivery date** (`orders.actual_delivery_date`). The delivery day is **day 0**. A request made on day N is in time if N is less than or equal to the window.

| Reason for refund | Window under v1 | Conditions |
|---|---|---|
| Change of mind (item is returnable, unused, complete, original packaging) | **10 days** | Product must have `products.returnable = true`. Loyalty extension may apply (section 7). |
| Product defective / dead on arrival | **15 days** | Photo or video evidence; item must be returned for QC. |
| Product damaged in transit | **15 days** | Photos of the item **and** outer packaging. |
| Wrong item delivered | **15 days** | Photos of the item and its label. Original item must be returned. |
| Item missing from the package | **15 days** | Reported with photo of the package as received. Refund is limited to the missing item. |
| Order not delivered / lost in transit | Claim allowed from ETA + 7 days, until 30 days after `estimated_delivery_date` | Only if delivery status is not "delivered". See Shipping Policy for "delivered but not received". |
| Order cancelled before shipment (prepaid) | Automatic | See Cancellation Policy. |
| Duplicate or excess charge | 30 days from the charge date | Verified against payment records. |

Late delivery by itself is **not** a ground for refund (a goodwill credit may apply - see Shipping Policy).

## 4. Refund amount
1. **Items:** refund = amount actually paid for the item = `order_items.final_price` (after discounts) **plus the GST charged on that item** (18%).
2. **Shipping fee** is refunded only when (a) the **whole order** is cancelled before shipment, or (b) the whole order is returned because of a wrong, damaged or defective item, or (c) the order is lost in transit. A partial return never refunds shipping.
3. **Cap:** a refund can never exceed the amount paid for the item(s) concerned, and total refunds on an order can never exceed `orders.total_amount`. Customers sometimes ask for more (for "trouble", "time", "compensation"). Such amounts are **not payable**; the agent should state the maximum refundable amount.
4. **Coupons:** discounts are not refunded as cash; the refund is net of the discount that was applied.
5. **Restocking fee:** none under v1.

## 5. Refund method and timelines
- Refunds go **only to the original payment method** (see Payment Policy). Cash-on-delivery orders are refunded to the NovaMart wallet or to a verified bank account.
- Refunds are released **within 3 business days after the returned item passes QC** (for cancellations: immediately).
- Time to appear: wallet - instant; UPI - 1-3 business days; debit/credit card and net banking - 5-7 business days.

## 6. Approval requirements
| Situation | Who can approve |
|---|---|
| Order total (`orders.total_amount`) of **INR 1,00,000 or less** and all conditions met | Tier 1 agent / AI agent may initiate |
| Order total **above INR 1,00,000** | **Human approval** by a Refund Approver is mandatory before the refund is released |
| Account status is `suspended` | Human review (Trust & Safety) |
| Refund to anything other than the original payment method | Not permitted. Escalate to Payments if the original instrument is unavailable. |
| Pattern of repeated claims (see Customer Escalation Policy) | Human review |

The threshold is evaluated on the **order total**, not on the value of the item being refunded.

## 7. Exceptions (legitimate)
1. **Loyalty extension (change of mind only):** Gold +2 days, Platinum +3 days on the change-of-mind window (`customers.loyalty_tier`).
2. **Request raised in time:** if the customer raised a return/refund/damage request (support ticket or chat) **inside** the window and the return could not be completed because of NovaMart or courier delay, eligibility is judged on the date of the original request (`support_tickets.created_at`), not today's date.
3. **Goodwill credit:** a Tier 1 agent may add up to INR 300 wallet credit for severe delivery delays (Shipping Policy). This is not a refund.
4. Any other exception requires a Support Lead.

## 8. Not refundable
Items with `returnable = false` (for change of mind), items returned damaged, incomplete or used beyond inspection, gift cards, and claims where evidence shows the customer's account is under investigation.

## 9. Escalate to a human when
- the order total exceeds the approval threshold in section 6;
- the account is suspended or the customer asks for a different refund destination;
- the customer disputes a delivery that is marked delivered with a verified OTP;
- statements are contradictory or evidence conflicts with the order record;
- the customer threatens legal action or reports a safety problem.

## 10. Worked examples
- Order placed 2026-04-02, delivered 2026-04-08, customer asks for change-of-mind refund on 2026-04-17 (day 9): **eligible** (window 10).
- Same order, request on 2026-04-20 (day 12): **not eligible** for change of mind; if the product is defective it is still inside the 15-day defect window.
- Order total INR 95,000, eligible return: the agent may initiate. Order total INR 1,10,000: escalate for approval.
