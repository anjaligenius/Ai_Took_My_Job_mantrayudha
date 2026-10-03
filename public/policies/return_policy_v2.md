# NovaMart Return Policy

| Field | Value |
|---|---|
| Policy | Return Policy |
| Version | v2 |
| **Effective date** | **2026-06-01** |
| Applies to | Orders **placed** on or after 2026-06-01 |
| Supersedes | Return Policy v1 (effective 2026-01-01), for those orders only |

## 1. Scope
How customers return products and what condition and process apply. **Time windows and refund amounts are defined in the Refund Policy of the same version** (Refund Policy v2: **7 days** change of mind, **10 days** defective/damaged/wrong item). The version is chosen by the order placement date (`orders.order_date`); orders placed before 2026-06-01 stay under Return Policy v1.

## 2. What can be returned
| Case | Allowed? |
|---|---|
| Change of mind, `returnable = true`, within the 7-day window (plus loyalty extension) | Yes |
| Change of mind, `returnable = false` | **No** - unless the product is defective |
| Defective / dead on arrival / damaged in transit / wrong item, within the 10-day defect window, with evidence | Yes - for all products |
| Used, missing accessories, serial/IMEI mismatch, liquid damage, physical damage caused after delivery | No (fails QC) |
| Gift cards, digital licences | No |

## 3. Conditions for a change-of-mind return
- Original packaging, all accessories, invoice; product unused / like new.
- Phones, tablets, laptops: accounts signed out, device locks removed, factory reset.
- Serial number / IMEI must match.
- Per-item returns are allowed in multi-item orders. **Shipping fees are not refunded on partial returns.**

## 4. Defective, damaged and wrong items
- Evidence is mandatory: photos/video of product, label/serial and outer packaging. A claim **without** evidence cannot be actioned - ask for it.
- Remedy: **replacement** where `products.replacement_available = true`, otherwise **refund**. The customer may choose a refund instead of a replacement.
- After the 10-day window a faulty product goes to Warranty (see Warranty Policy).

## 5. Process
1. A return request (ticket or chat) is logged; its timestamp is the **return request date**.
2. Pickup within 24-48 hours; two attempts.
3. QC within 2 business days after the warehouse receives the item.
4. QC pass: refund per Refund Policy v2. QC fail: item returned to customer, contest via Support Lead.

## 7. Restocking fee (new in v2)
Change-of-mind returns of **Laptops, Tablets, Cameras and Monitors**: **5% of the item refund, maximum INR 2,500**, deducted from the refund. No fee for defective/damaged/wrong-item returns or other categories.

## 8. Exceptions
1. **Loyalty extension** (change of mind only): Gold +2 days (9 days in total), Platinum +3 days (10 days in total).
2. **Requests raised in time:** if the customer raised a return request inside the window and pickup/processing was delayed by NovaMart or the courier, eligibility is judged on the original request date (earlier ticket's `created_at`), not on today's date.
3. Other exceptions: Support Lead only.

## 9. Escalation
Escalate when the order total exceeds INR 75,000 (see Refund Policy v2, section 6), when the account is suspended, when a QC outcome is disputed, or when the customer's story conflicts with the order record.

## 10. Differences from v1 (summary for agents)
Change-of-mind window 10 -> 7 days; defect window 15 -> 10 days; restocking fee introduced; approval threshold 1,00,000 -> 75,000 (in the Refund Policy). Do not apply v2 rules to orders placed before 2026-06-01.
