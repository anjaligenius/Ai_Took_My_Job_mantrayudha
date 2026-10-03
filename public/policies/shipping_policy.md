# NovaMart Shipping & Delivery Policy

| Field | Value |
|---|---|
| Policy | Shipping & Delivery Policy |
| Version | 1.0 (single version) |
| **Effective date** | **2026-01-01** |
| Applies to | All orders, all dates |

## 1. Delivery estimates
`orders.estimated_delivery_date` is the promised date shown at checkout. Typical transit: metro cities 3-5 days, other cities 5-8 days, remote pincodes up to 10 days. Orders are handed to the courier 1-3 days after placement.

## 2. Shipping fee
- Subtotal after discounts of **INR 1,000 or more: free shipping**.
- Below INR 1,000: **INR 79** flat.
- Shipping fee is refundable only as described in the Refund Policy.

## 3. Delivery verification (OTP)
- Orders with a total of **INR 5,000 or more** are delivered against a **one-time password** sent to the registered mobile (`orders.delivery_otp_verified = true` after hand-over).
- Lower-value orders may be left contactless; `delivery_otp_verified` is then usually `false`.
- An OTP-verified delivery is treated as proof of hand-over to the person who holds the registered phone.

## 4. Delays
| Delay beyond ETA | What the agent may do |
|---|---|
| 1-3 days | Apologise, share tracking and revised ETA. |
| More than 3 days | Goodwill **wallet credit of INR 100 for each full 3 days** late, **maximum INR 300**, issued by a Tier 1 agent. |
| More than 7 days, no movement | Treat as **suspected lost in transit**: open a Logistics ticket; refund or replacement is decided after the courier investigation (up to 72 hours). Do not promise an immediate refund. |

Lateness alone is not a reason for a refund while the parcel is still moving.

## 5. "Delivered but not received"
1. **OTP verified** (`delivery_otp_verified = true`): do **not** refund or replace. Escalate to the Logistics investigations team; they contact the customer within 3 business days (courier proof-of-delivery, geo-tag, recipient check).
2. **Delivered without OTP**, reported within 48 hours of delivery: open a delivery investigation with the courier. If the parcel is not traced within 5 business days, a refund or replacement is arranged (a human approves it if it exceeds the approval threshold).
3. **Delivered without OTP, reported after 48 hours:** open an investigation; refund/replacement is a human decision.
4. **Repeated claims:** three or more non-delivery or refund claims by the same customer in the last 90 days -> escalate to Trust & Safety regardless of OTP status (see Customer Escalation Policy).
5. If the order is not yet delivered, the claim is a delay - use section 4.

## 6. Address changes
- Before shipment (`placed`, `confirmed`, `processing`): the address can be changed once; confirm the full new address and pincode.
- After shipment: not possible. The customer may reschedule with the courier, refuse the delivery or arrange collection from the courier hub. NovaMart cannot redirect a shipped parcel to another city.

## 7. Failed delivery attempts
Three attempts are made. After the third failed attempt the parcel returns to NovaMart and is refunded (prepaid) or closed (COD).

## 8. Couriers
BlueArrow Express, SwiftLane, KaveriCargo, DeltaPost, RoadRunner Logistics. Tracking numbers start with the courier's code (BAX, SLN, KVC, DLP, RRL). Tracking details may be shared only with the account holder who owns the order.
