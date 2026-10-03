# NovaMart Return Policy

| Field | Value |
|---|---|
| Policy | Return Policy |
| Version | v1 |
| **Effective date** | **2026-01-01** |
| Applies to | Orders **placed** from 2026-01-01 up to and including 2026-05-31 |
| Superseded by | Return Policy v2 (effective 2026-06-01) for orders placed on or after that date |

## 1. Scope
How customers return products and what condition and process apply. **Time windows and refund amounts are defined in the Refund Policy of the same version** (Refund Policy v1: 10 days change of mind, 15 days defective/damaged/wrong item). The version is chosen by the order placement date (`orders.order_date`).

## 2. What can be returned
| Case | Allowed? |
|---|---|
| Change of mind, product marked `returnable = true`, within window | Yes |
| Change of mind, product marked `returnable = false` (e.g. in-ear earbuds, opened accessories such as cases, screen protectors, cables) | **No** - unless the product is defective |
| Defective / dead on arrival / damaged in transit / wrong item, within the defect window, with evidence | Yes, for all products, including those with `returnable = false` |
| Used, scratched, missing accessories, serial/IMEI mismatch, water damage | No (fails QC) |
| Items bought as a gift card or digital licence | No |

## 3. Conditions for a change-of-mind return
- Original packaging, all accessories and invoice included; product unused or in "like new" condition.
- Phones, tablets and laptops: account sign-outs and "Find my device" locks removed, device factory reset.
- Serial number / IMEI must match the unit shipped.
- Returns are accepted **per item**: customers may return one item of a multi-item order.

## 4. Defective, damaged and wrong items
- Evidence is mandatory: photos (and video for dead-on-arrival units) of the product, label/serial and outer packaging.
- NovaMart offers a **replacement** where `products.replacement_available = true` (see Replacement Policy) or a **refund** otherwise or on customer preference.
- A faulty product reported **after** the defect window is handled under the Warranty Policy.

## 5. Process
1. Customer or agent raises a return request (ticket). The request time stamp counts as the return request date.
2. Pickup scheduled within 24-48 hours; two pickup attempts.
3. QC at the warehouse within 2 business days of receipt.
4. QC pass: refund released per Refund Policy. QC fail: item is sent back; customer may contest through a Support Lead.

## 6. Restocking fee
None under v1.

## 7. Exceptions
1. **Loyalty extension** on the change-of-mind window: Gold +2 days, Platinum +3 days.
2. **Requests raised in time:** where the customer raised the return inside the window and pickup or processing was delayed by NovaMart or the courier, the original request date is used (look at `support_tickets.created_at` for the earlier ticket).
3. Other exceptions: Support Lead only.

## 8. Escalation
Escalate when the order total is above the approval threshold of the applicable Refund Policy, when the account is suspended, when QC results are disputed, or when the customer's account of events conflicts with the order record.
