# NovaMart Cancellation Policy

| Field | Value |
|---|---|
| Policy | Cancellation Policy |
| Version | 1.0 (single version) |
| **Effective date** | **2026-01-01** |
| Applies to | All orders, all dates |

## 1. When an order can be cancelled
Cancellation depends on the order's progress at the moment of the request:

| `orders.order_status` | Can the customer cancel? | Notes |
|---|---|---|
| `placed`, `confirmed`, `processing` | **Yes** (whole order, or one item of a multi-item order) | No tracking number exists yet; the parcel has not been handed to the courier. |
| `shipped`, `out_for_delivery` | **No** | Offer: refuse the delivery at the door (order returns to NovaMart and is refunded), or return after delivery under the Return Policy. A cancellation request is logged as `cancellation_status = rejected`. |
| `delivered`, `returned`, `partially_returned` | **No** | Use the Return/Refund Policy instead. |
| `cancelled` | Already cancelled | Check refund status. |

A tracking number (`orders.tracking_number`) means the order was handed to a courier.

## 2. How cancellation works
1. Confirm the **order ID** (or unambiguous product + date) with the customer. If the customer has several cancellable orders and does not say which, **ask**.
2. Cancel the order. `order_status` becomes `cancelled`, `cancellation_status` becomes `approved`.
3. Prepaid orders are refunded **in full, including the shipping fee**, to the original payment method: wallet instant, UPI 1-3 business days, cards/net banking 5-7 business days.
4. Cash-on-delivery orders have nothing to refund.
5. Cancellation before shipment never needs human approval, whatever the order value.

## 3. Cancellations initiated by NovaMart
NovaMart may cancel an order for stock-out, unserviceable pincode, failed or unconfirmed payment (prepaid payment still pending after 24 hours), or suspected fraud. `cancellation_status = auto_cancelled` indicates a system cancellation (for example payment failure). Customers are refunded in full. The order table does not record a detailed reason; do not invent one.

## 4. Duplicate orders
If two identical orders were placed minutes apart and are both unshipped, cancel the later duplicate on request and refund it. Never cancel both unless the customer asks.

## 5. Abuse limits
More than 5 cancellations by the same customer within 30 days: flag for review (Customer Escalation Policy). Cancellation must not be used to reverse a delivered order.

## 6. Partial cancellation
Allowed only while status is `placed` or `confirmed` for orders with more than one item. Shipping fee is refunded only if the whole order is cancelled.
