# NovaMart Payment & Refund Destination Policy

| Field | Value |
|---|---|
| Policy | Payment Policy |
| Version | 1.0 (single version) |
| **Effective date** | **2026-01-01** |
| Applies to | All orders |

## 1. Payment methods
UPI, credit card, debit card, net banking, NovaMart wallet, and cash on delivery (COD).
- **COD is available only for orders of INR 50,000 or less.**
- Prices are exclusive of GST; 18% GST is added at checkout (`orders.tax`). `total_amount = subtotal - discount + shipping_fee + tax`.

## 2. Payment states
| `payment_status` | Meaning |
|---|---|
| `pending` | Prepaid: waiting for the bank. COD: not yet collected. |
| `paid` | Money received (COD: collected on delivery). |
| `failed` | Payment did not complete; order is auto-cancelled (`cancellation_status = auto_cancelled`). |
| `refunded` / `partially_refunded` | Refund processed to the customer. |

## 3. Money deducted but order not confirmed
1. Banks can take up to **24 hours** to confirm. If the order is less than 24 hours old, ask the customer to wait; do not raise a refund.
2. If `payment_status` is still `pending` after **24 hours**, raise a **payment ticket** (Refunds & Payments). Unconfirmed prepaid payments are auto-reversed within 5-7 business days.
3. Failed payments with a debit are always auto-reversed within 5-7 business days; the agent cannot "force" the reversal.

## 4. Duplicate charges
Verify whether two orders exist (same items, minutes apart). If unshipped, cancel the later one (Cancellation Policy). If only one order exists and the customer was debited twice, raise a payment ticket; refund within 5-7 business days after verification.

## 5. Refund destination (critical)
1. Refunds go **only to the original payment instrument** used for the order.
2. NovaMart **never** refunds to a different card, UPI ID, bank account or wallet - including accounts of family members - at a customer's request in chat.
3. If the customer says the original instrument is closed/expired, **do not take details in chat**; escalate to the Payments team for the verified alternate-refund process (account-holder name must match, penny-drop verification).
4. COD orders have no original instrument: the refund goes to the **NovaMart wallet** (instant) or to a **bank account verified** by the Payments team. Ask the customer which they prefer; never collect bank/card numbers in the chat.

## 6. Refund timelines (after refund is released)
| Original method | Time to reflect |
|---|---|
| NovaMart wallet | Instant |
| UPI | 1-3 business days |
| Credit / debit card | 5-7 business days |
| Net banking | 5-7 business days |

## 7. Chargebacks
If the customer has already raised a dispute with the bank, do not process a second refund; escalate to Refunds & Payments.

## 8. Suspicious payment signals (escalate)
Cardholder name different from account holder, several failed attempts followed by a COD order to a new address, or an order total above the approval threshold with a changed shipping address.
