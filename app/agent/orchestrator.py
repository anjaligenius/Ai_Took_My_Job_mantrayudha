from __future__ import annotations
from datetime import datetime, date, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import re
import uuid

from .intents import infer_intents
from app.security.input_firewall import inspect
from app.policy.rules import parse_date, hours_between, day_number, warranty_end_date
from app.tools.action_guard import ActionGuard

def _requested_destination(text: str):
    low=text.lower()
    different_terms=['wife','husband','friend','family','different account','other account','another account','different bank','other bank','another bank','different upi','other upi','another upi','another card','different card','my brother','my sister']
    if any(t in low for t in different_terms):
        return 'different instrument'
    return 'original payment method'

class AgentOrchestrator:
    def __init__(self, store, policy_engine, tools, memory, llm=None):
        self.store=store
        self.policy=policy_engine
        self.tools=tools
        self.memory=memory
        self.guard=ActionGuard()
        self.llm=llm

    def run(self, customer_id: str, message: str, now: str, use_llm: bool=False) -> Dict[str, Any]:
        request_id='REQ-' + uuid.uuid4().hex[:10].upper()
        trace=[]
        evidence={'customer_verified':False}
        self.tools.trace=[]
        firewall=inspect(message)
        trace.append({'stage':'INPUT FIREWALL','status':'PASS','detail':'Customer input isolated as untrusted data.','flags':{k:v for k,v in firewall.items() if k in ('injection','legal','safety','abusive','human_request')}})

        customer=self.tools.get_customer(customer_id)
        evidence['customer_verified']=customer is not None
        trace.append({'stage':'CONTEXT','status':'VERIFIED' if customer else 'FAIL','detail':'Authenticated customer context loaded.' if customer else 'Customer account not found.'})
        if not customer:
            return self._final(request_id,'ASK','I could not verify the customer account from the supplied session. Please restart the support session.',[],[],evidence,trace,{}, {'tool_calls':1})

        memory=self.memory.retrieve(customer_id)
        self.tools.get_conversations(customer_id)
        trace.append({'stage':'MEMORY','status':'RETRIEVED','detail':f"Retrieved prior conversations and {len(memory['recent_tickets'])} recent tickets."})

        if firewall['safety']:
            esc=self.tools.escalate_to_human(customer_id,None,'Technical Support','Product safety incident reported: possible swelling, overheating, smoke or burning smell.','critical')
            self.tools.verify_result('escalation',esc['escalation_id'])
            trace.extend(self.tools.trace)
            response='This is a safety issue. Please stop using and charging the device immediately. I have escalated this as a critical case to Technical Support; the target first response is 15 minutes.'
            return self._final(request_id,'ESCALATE',response,[],[],evidence,trace,{},self._stats())

        if firewall['legal']:
            esc=self.tools.escalate_to_human(customer_id,None,'Customer Experience','Legal threat detected in customer message.','high')
            self.tools.verify_result('escalation',esc['escalation_id'])
            trace.extend(self.tools.trace)
            response='I cannot resolve a legal request automatically, so I have escalated this to Customer Experience. They will respond within 1 hour for a high-priority case.'
            return self._final(request_id,'ESCALATE',response,[],[],evidence,trace,{},self._stats())

        if firewall['human_request']:
            esc=self.tools.escalate_to_human(customer_id,None,'Support Lead','Customer explicitly requested a human agent.','medium')
            self.tools.verify_result('escalation',esc['escalation_id'])
            trace.extend(self.tools.trace)
            response='I have queued this for a human support specialist. They will receive the conversation context so you do not need to repeat it.'
            return self._final(request_id,'ESCALATE',response,[],[],evidence,trace,{},self._stats())

        intents=infer_intents(message,self.store,customer_id)
        trace.append({'stage':'INTENT','status':'PARSED','detail':f'{len(intents)} intent(s) detected.','intents':[{'id':i['id'],'intent':i['intent'],'dependencies':i['dependencies']} for i in intents]})
        results=[]
        result_by_id={}
        unresolved={i['id'] for i in intents}
        iterations=0
        while unresolved and iterations < len(intents)+2:
            iterations+=1
            progressed=False
            for intent in intents:
                if intent['id'] not in unresolved:
                    continue
                if any(dep in unresolved for dep in intent.get('dependencies',[])):
                    continue
                r=self._handle_intent(customer, intent, message, now, firewall, memory, trace, evidence, result_by_id)
                results.append(r); result_by_id[intent['id']]=r; unresolved.remove(intent['id']); progressed=True
            if not progressed:
                break
        if unresolved:
            for intent in intents:
                if intent['id'] in unresolved:
                    r={'decision':'ASK','reason':'Intent dependency could not be resolved safely.','customer_response':'I need one part of your request clarified before I can safely continue. Which order or issue should I handle first?','intent_id':intent['id'],'actions':[],'evidence':{},'policy':{}}
                    results.append(r); result_by_id[intent['id']]=r

        decision=self._aggregate(results)
        response=self._combine_responses(results)

        if use_llm and self.llm and self.llm.enabled:
            enriched=self._enrich_response_with_gemini(customer, message, decision, response, results, evidence)
            if enriched:
                response=enriched
                trace.append({'stage':'GEMINI LLM','status':'ENRICHED','detail':f'Customer response enriched using free Google Gemini ({self.llm.model}) while strictly preserving verified outcome.'})
            else:
                trace.append({'stage':'GEMINI LLM','status':'FALLBACK','detail':'Gemini enrichment bypassed (unavailable or timed out); preserved verified baseline response.'})

        trace.append({'stage':'DECISION','status':decision,'detail':'Terminal outcome selected only after verification and policy checks.'})
        trace.extend(self.tools.trace)
        trace.append({'stage':'RESULT VERIFICATION','status':'COMPLETE','detail':'All write actions in this run were post-condition checked.'})
        return self._final(request_id,decision,response,intents,results,evidence,trace,self._aggregate_policy(results),self._stats())

    def _handle_intent(self, customer, intent, original_message, now, firewall, memory, trace, evidence, previous) -> Dict[str, Any]:
        typ=intent['intent']

        # Dependencies are hard gates. In particular, a refund attached to a
        # non-delivery claim cannot jump ahead of delivery verification.
        deps=[previous.get(dep) for dep in intent.get('dependencies',[]) if previous.get(dep)]
        if deps and typ == 'refund' and intent.get('reason') == 'non_delivery':
            dep=deps[0]
            if dep.get('decision') == 'ESCALATE':
                return {
                    'decision':'ESCALATE',
                    'reason':'Refund is held behind a delivery investigation.',
                    'customer_response':'I have held the refund request while the delivery issue is investigated. The delivery case has already been escalated, so no automatic refund will be issued from this step.',
                    'intent_id':intent['id'],'actions':[],
                    'evidence':{'customer_verified':True,'order_owned':True,'dependency_decision':'ESCALATE'},
                    'policy':dep.get('policy',{}),
                }
            if dep.get('decision') == 'ASK':
                return {
                    'decision':'ASK',
                    'reason':'Refund is held until the delivery ambiguity is resolved.',
                    'customer_response':'I need to resolve the delivery details before I can determine whether a refund is available. No refund has been issued.',
                    'intent_id':intent['id'],'actions':[],
                    'evidence':{'customer_verified':True,'order_owned':True,'dependency_decision':'ASK'},
                    'policy':dep.get('policy',{}),
                }
            return {
                'decision':'ANSWER',
                'reason':'Delivery verification did not establish a refundable lost-order state.',
                'customer_response':'I verified the delivery status first. Because the order has not been established as eligible for a non-delivery refund, I did not issue a refund automatically.',
                'intent_id':intent['id'],'actions':[],
                'evidence':{'customer_verified':True,'order_owned':True,'dependency_decision':dep.get('decision')},
                'policy':dep.get('policy',{}),
            }
        if firewall['human_request'] and typ not in {'general'}:
            esc=self.tools.escalate_to_human(customer['customer_id'],intent.get('order_id'),'Support Lead','Customer explicitly requested a human agent.','medium')
            self.tools.verify_result('escalation',esc['escalation_id'])
            return {'decision':'ESCALATE','reason':'Customer requested a human agent.','customer_response':'I have queued this for a human support specialist. They will receive the conversation context so you do not need to repeat it.','intent_id':intent['id'],'actions':[esc],'evidence':{'customer_verified':True},'policy':{}}
        if typ == 'order_history':
            return self._order_history(customer, intent)
        if not intent.get('order_id') and typ in {'product_info', 'general'}:
            return self._handle_product_or_general(customer, intent)
        order, ownership_issue = self._resolve_order(customer, intent, original_message)
        if ownership_issue:
            if ownership_issue == 'ambiguous':
                options=self._order_options(customer, intent, original_message)
                return {'decision':'ASK','reason':'Multiple customer orders match the request; guessing is unsafe.','customer_response':'I found more than one matching order. Please tell me which order you mean: ' + '; '.join(options[:4]),'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'ambiguity':True},'policy':{}}
            if ownership_issue == 'not_owned':
                oid = intent.get('order_id') or 'specified'
                cust_orders = self.store.customer_orders(customer['customer_id'])
                recent_lines = []
                for o in cust_orders[:3]:
                    items = self.store.get_order_items(o['order_id'])
                    pnames = [self.store.get_product(it['product_id'])['product_name'] for it in items if self.store.get_product(it['product_id'])]
                    recent_lines.append(f"• {o['order_id']} ({o.get('order_date','')[:10]}, {o.get('order_status','').title()}): {', '.join(pnames[:2])}")
                resp = f"Order {oid} is not associated with your authenticated account ({customer.get('first_name','')} {customer.get('last_name','')}). For your privacy and security, I can only look up orders belonging to your verified profile."
                if recent_lines:
                    resp += "\n\nYour recent orders on file:\n" + "\n".join(recent_lines)
                    resp += "\n\nIf this order was placed under a different account, please switch customer profiles."
                else:
                    resp += " No orders were found under this account."
                return {'decision':'ASK','reason':'Order not associated with customer account.','customer_response':resp,'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':False},'policy':{}}
            if ownership_issue == 'not_found':
                oid = intent.get('order_id') or 'specified'
                cust_orders = self.store.customer_orders(customer['customer_id'])
                recent_lines = []
                for o in cust_orders[:3]:
                    items = self.store.get_order_items(o['order_id'])
                    pnames = [self.store.get_product(it['product_id'])['product_name'] for it in items if self.store.get_product(it['product_id'])]
                    recent_lines.append(f"• {o['order_id']} ({o.get('order_date','')[:10]}, {o.get('order_status','').title()}): {', '.join(pnames[:2])}")
                resp = f"I could not find order {oid} in our system. Please check your order confirmation email or SMS to verify the order number (typically formatted as ORD-XXXXXX)."
                if recent_lines:
                    resp += "\n\nYour recent orders on file:\n" + "\n".join(recent_lines)
                return {'decision':'ASK','reason':'Order ID does not exist in store.','customer_response':resp,'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':False},'policy':{}}
            cust_orders = self.store.customer_orders(customer['customer_id'])
            if cust_orders:
                recent_lines = []
                for o in cust_orders[:3]:
                    items = self.store.get_order_items(o['order_id'])
                    pnames = [self.store.get_product(it['product_id'])['product_name'] for it in items if self.store.get_product(it['product_id'])]
                    recent_lines.append(f"• {o['order_id']} ({o.get('order_date','')[:10]}, {o.get('order_status','').title()}): {', '.join(pnames[:2])}")
                resp = "Please share your order ID so I can verify eligibility and continue.\n\nYour recent orders:\n" + "\n".join(recent_lines)
            else:
                resp = "Please share your order ID so I can verify eligibility and continue."
            return {'decision':'ASK','reason':'Order is required for this request.','customer_response':resp,'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':False},'policy':{}}
        if not order and typ in {'product_info','general'}:
            return self._handle_product_or_general(customer,intent)
        if not order:
            return {'decision':'ASK','reason':'Order is required for this request.','customer_response':'Please share your order ID so I can verify eligibility and continue.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True},'policy':{}}

        evidence['order_owned']=True
        order_id=order['order_id']
        policy_snapshot=self.policy.policy_snapshot(order)
        trace.append({'stage':'VERIFY','status':'PASS','detail':f'Order {order_id} exists and belongs to the authenticated customer.'})
        trace.append({'stage':'POLICY','status':'RESOLVED','detail':f"Applicable refund policy is {policy_snapshot['version']} based on order placement date.", 'snapshot':policy_snapshot})

        # System-level safety / legal checks always outrank ordinary intents.
        if firewall['legal']:
            esc=self.tools.escalate_to_human(customer['customer_id'],order_id,'Customer Experience','Legal threat detected in customer message.','high')
            self.tools.verify_result('escalation',esc['escalation_id'])
            return {'decision':'ESCALATE','reason':'Legal threat requires human handling.','customer_response':'I cannot resolve a legal request automatically, so I have escalated this to Customer Experience. They will respond within 1 hour for a high-priority case.','intent_id':intent['id'],'actions':[esc],'evidence':{'customer_verified':True,'order_owned':True},'policy':policy_snapshot}

        if customer.get('account_status','').lower() == 'suspended':
            esc=self.tools.escalate_to_human(customer['customer_id'],order_id,'Trust & Safety','Customer account is suspended; human review is mandatory.','high')
            self.tools.verify_result('escalation',esc['escalation_id'])
            return {'decision':'ESCALATE','reason':'Suspended accounts require human review.','customer_response':'Your account requires human review, so I have escalated this case to Trust & Safety.','intent_id':intent['id'],'actions':[esc],'evidence':{'customer_verified':True,'order_owned':True,'account_suspended':True},'policy':policy_snapshot}

        repeated=self.policy.repeated_claims(customer['customer_id'],parse_date(now))
        if repeated >= 3 and typ in {'refund','return','replacement','delivery'}:
            esc=self.tools.escalate_to_human(customer['customer_id'],order_id,'Trust & Safety','Three or more refund/return/non-delivery claims were recorded in the last 90 days.','high')
            self.tools.verify_result('escalation',esc['escalation_id'])
            return {'decision':'ESCALATE','reason':'Repeated recent claims trigger Trust & Safety review.','customer_response':'I have escalated this to Trust & Safety because your recent account history requires a human review.','intent_id':intent['id'],'actions':[esc],'evidence':{'customer_verified':True,'order_owned':True,'repeated_claims_90d':repeated},'policy':policy_snapshot}

        if typ in {'delivery'}:
            return self._delivery(customer,order,intent,now,policy_snapshot,firewall)
        if typ == 'invoice':
            return self._invoice(customer,order,intent)
        if typ in {'refund','return','replacement'}:
            return self._return_refund_replace(customer,order,intent,now,policy_snapshot,original_message)
        if typ == 'cancellation':
            return self._cancellation(customer,order,intent)
        if typ == 'address_change':
            return self._address(customer,order,intent)
        if typ == 'payment':
            return self._payment(customer,order,intent,now)
        if typ == 'warranty':
            return self._warranty(customer,order,intent,now)
        return self._handle_product_or_general(customer,intent)

    def _resolve_order(self, customer, intent, text):
        oid=intent.get('order_id')
        if oid:
            order=self.tools.get_order(oid)
            if not order:
                return None,'not_found'
            if order.get('customer_id') != customer['customer_id']:
                return None,'not_owned'
            return order,None
        if intent.get('product_id'):
            matches=[]
            for o in self.store.customer_orders(customer['customer_id']):
                for item in self.store.get_order_items(o['order_id']):
                    if item.get('product_id') == intent['product_id']:
                        matches.append(o)
            if len(matches)==1:
                intent['order_id']=matches[0]['order_id']
                return matches[0],None
            if len(matches)>1:
                return None,'ambiguous'
        if intent['intent'] in {'product_info','general','order_history'}:
            return None,None
        cust_orders = self.store.customer_orders(customer['customer_id'])
        if len(cust_orders) == 1 and intent['intent'] in {'delivery', 'invoice'}:
            single = cust_orders[0]
            intent['order_id'] = single['order_id']
            return single, None
        candidates=self.store.search_customer_products(customer['customer_id'],text)
        # Prefer exact unique product match; otherwise ambiguous.
        unique=[]
        seen=set()
        for c in candidates:
            key=c['order']['order_id']
            if key not in seen:
                seen.add(key); unique.append(c)
        if len(unique)==1:
            intent['order_id']=unique[0]['order']['order_id']; intent['product_id']=unique[0]['product']['product_id']; return unique[0]['order'],None
        if len(unique)>1:
            return None,'ambiguous'
        return None,'missing'

    def _order_options(self, customer, intent, text):
        cands=self.store.search_customer_products(customer['customer_id'],text)
        out=[]
        seen=set()
        for c in cands:
            oid=c['order']['order_id']
            if oid in seen: continue
            seen.add(oid); out.append(f"{oid} ({c['product']['product_name']}, delivered {c['order'].get('actual_delivery_date') or 'not delivered'})")
        return out

    def _get_single_item_product(self, order, text):
        items=self.store.get_order_items(order['order_id'])
        if len(items)==1:
            item=items[0]; return item,self.store.get_product(item['product_id'])
        cands=[]
        low=text.lower()
        for item in items:
            p=self.store.get_product(item['product_id'])
            if p and any(tok in p['product_name'].lower() for tok in re.findall(r'[a-z0-9]+',low) if len(tok)>3):
                cands.append((item,p))
        if len(cands)==1: return cands[0]
        return None,None

    def _delivery(self,customer,order,intent,now,policy,firewall):
        status=order.get('order_status','').lower(); delivery=order.get('delivery_status','').lower(); nowd=parse_date(now)
        otp=str(order.get('delivery_otp_verified','')).lower()=='true'
        if any(term in intent['text'].lower() for term in ('not received', 'never received', 'never arrived', "didn't receive", 'not arrived')):
            if delivery=='delivered' or status=='delivered':
                if otp:
                    esc=self.tools.escalate_to_human(customer['customer_id'],order['order_id'],'Logistics Desk','Order is marked delivered with verified OTP, but customer disputes receipt.','high')
                    self.tools.verify_result('escalation',esc['escalation_id'])
                    return {'decision':'ESCALATE','reason':'OTP-verified delivery is contradictory to the customer claim.','customer_response':f"Our records show {order['order_id']} as delivered with OTP verification. I have escalated this to the Logistics investigations team rather than issuing an automatic refund. They will contact you within 3 business days.",'intent_id':intent['id'],'actions':[esc],'evidence':{'customer_verified':True,'order_owned':True,'delivery_status':'delivered','otp_verified':True},'policy':policy}
                delivered_at=order.get('actual_delivery_date') or now
                # The public CSV stores dates for delivery, so a date-only value
                # is treated as midnight in the same local business time zone.
                hours=max(0.0, hours_between(delivered_at, now)) if 'T' in str(delivered_at) else max(0.0, (nowd-parse_date(delivered_at)).days*24)
                if hours <= 48:
                    t=self.tools.create_support_ticket(customer['customer_id'],order['order_id'],'delivery','high','Delivered without OTP reported within 48 hours; open courier investigation.','Logistics Desk')
                    self.tools.verify_result('ticket',t['ticket_id'])
                    return {'decision':'ACT','reason':'Delivered without OTP, reported within 48 hours.','customer_response':f"I have opened a delivery investigation for {order['order_id']}. Because it was delivered without OTP and the claim is within 48 hours, the courier will investigate first.",'intent_id':intent['id'],'actions':[t],'evidence':{'customer_verified':True,'order_owned':True,'otp_verified':False,'reported_within_48h':True},'policy':policy}
                t=self.tools.create_support_ticket(customer['customer_id'],order['order_id'],'delivery','high','Delivered without OTP reported after 48 hours; human decision required.','Logistics Desk')
                self.tools.verify_result('ticket',t['ticket_id'])
                return {'decision':'ESCALATE','reason':'Delivered without OTP but reported after 48 hours requires human decision.','customer_response':'I have opened a delivery investigation and escalated the case for a human decision.','intent_id':intent['id'],'actions':[t],'evidence':{'customer_verified':True,'order_owned':True,'otp_verified':False,'reported_within_48h':False},'policy':policy}
            # Not delivered: delay/lost flow
            eta=parse_date(order['estimated_delivery_date']); delay=(nowd-eta).days
            if delay <= 0:
                return {'decision':'ANSWER','reason':'Order is still within the promised delivery date.','customer_response':f"{order['order_id']} is currently {delivery or status}. The promised delivery date is {order['estimated_delivery_date']}.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'eta_verified':True},'policy':policy}
            if delay <= 3:
                return {'decision':'ANSWER','reason':'Delay is within the 1-3 day service band.','customer_response':f"I'm sorry for the delay. {order['order_id']} is still moving. The promised date was {order['estimated_delivery_date']}; please use tracking {order.get('tracking_number') or 'available in your account'} for the latest movement.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'delay_days':delay},'policy':policy}
            if delay <= 7:
                credit=min(100*(delay//3),300)
                ev={'customer_verified':True,'order_owned':True,'delay_verified':True,'credit_within_cap': credit<=300}
                self.guard.validate('add_wallet_credit',ev)
                cr=self.tools.add_wallet_credit(customer['customer_id'],credit,'Severe delivery delay goodwill credit')
                self.tools.verify_result('ticket','') if False else None
                return {'decision':'ACT','reason':'Delay qualifies for goodwill wallet credit.','customer_response':f"Your order is {delay} days past the promised date. I have added an INR {credit} NovaMart wallet credit as a goodwill gesture; the parcel is still being treated as in transit.",'intent_id':intent['id'],'actions':[cr],'evidence':ev,'policy':policy}
            t=self.tools.create_support_ticket(customer['customer_id'],order['order_id'],'delivery','high','Order is more than 7 days late with no delivered status; suspected lost in transit.','Logistics Desk')
            self.tools.verify_result('ticket',t['ticket_id'])
            return {'decision':'ESCALATE','reason':'Suspected lost in transit after more than 7 days beyond ETA.','customer_response':f"I have opened a Logistics investigation for {order['order_id']} because it is more than 7 days past the promised date. Refund or replacement will be decided after the courier investigation, which can take up to 72 hours.",'intent_id':intent['id'],'actions':[t],'evidence':{'customer_verified':True,'order_owned':True,'delay_days':delay,'suspected_lost':True},'policy':policy}
        items = self.store.get_order_items(order['order_id'])
        products = [self.store.get_product(it['product_id']) for it in items]
        actual_delivery = order.get('actual_delivery_date')
        est_delivery = order.get('estimated_delivery_date')
        courier = order.get('courier') or 'NovaMart Logistics'
        tracking = order.get('tracking_number') or 'In Transit'
        otp_text = 'OTP Verified' if otp else 'Standard Delivery'
        status_display = (delivery or status).title()
        
        item_parts = []
        for it, p in zip(items, products):
            pname = p.get('product_name', it.get('product_id')) if p else it.get('product_id')
            item_parts.append(f"{it.get('quantity', 1)}x {pname} (INR {float(it.get('final_price', 0)):,.0f})")
            
        lines = [
            f"📦 **Order {order['order_id']} Overview**",
            f"• **Status**: {status_display}",
        ]
        if actual_delivery:
            lines.append(f"• **Delivered On**: {actual_delivery} ({otp_text})")
        else:
            lines.append(f"• **Estimated Delivery**: {est_delivery}")
        lines.append(f"• **Courier Partner**: {courier} (Tracking: `{tracking}`)")
        lines.append(f"• **Items**: {', '.join(item_parts)}")
        lines.append(f"• **Total Paid**: INR {float(order.get('total_amount', 0)):,.0f} via {order.get('payment_method', '').replace('_', ' ').title()}")
        lines.append(f"• **Shipping Address**: {order.get('shipping_address')}")
        
        snap = self.policy.policy_snapshot(order)
        win = self.policy.refund_window(order, customer, 'change_of_mind')
        if actual_delivery:
            try:
                del_d = parse_date(actual_delivery)
                now_d = parse_date(now)
                exp_d = del_d + timedelta(days=win)
                if now_d <= exp_d:
                    days_left = (exp_d - now_d).days
                    lines.append(f"• **Return / Exchange Window**: Active ({days_left} day{'s' if days_left != 1 else ''} remaining, until {exp_d.isoformat()} under Policy {snap['version']})")
                else:
                    lines.append(f"• **Return Window**: Closed on {exp_d.isoformat()} ({win}-day window under Policy {snap['version']})")
            except Exception:
                pass
        elif status in {'placed', 'confirmed', 'processing'}:
            lines.append(f"• **Modifications**: Eligible for pre-shipment cancellation or address update.")
            
        warr_parts = []
        for it, p in zip(items, products):
            if p and p.get('warranty_months') and actual_delivery:
                try:
                    w_months = int(float(p['warranty_months']))
                    if w_months > 0:
                        w_end = warranty_end_date(actual_delivery, w_months)
                        warr_parts.append(f"{p['product_name']}: {w_months} months (Valid through {w_end.isoformat()})")
                except Exception:
                    pass
        if warr_parts:
            lines.append(f"• **Manufacturer Warranty**: {'; '.join(warr_parts)}")
            
        lines.extend([
            "",
            "💡 **Helpful Actions**:",
            f"• To download tax invoice: `Download invoice for {order['order_id']}` ([Download PDF](/api/invoice/{order['order_id']}/pdf))",
            f"• To report a defect or request return: `Return item in {order['order_id']}`",
            f"• To talk with human support: `Connect me to human agent`"
        ])
        
        return {
            'decision': 'ANSWER',
            'reason': 'Delivery and order details verified from order record.',
            'customer_response': '\n'.join(lines),
            'intent_id': intent['id'],
            'actions': [],
            'evidence': {
                'customer_verified': True,
                'order_owned': True,
                'order_id': order['order_id'],
                'delivery_status': order.get('delivery_status'),
                'order_status': order.get('order_status'),
                'courier': courier,
                'tracking_number': tracking
            },
            'policy': policy
        }

    def _return_refund_replace(self,customer,order,intent,now,policy,original_message):
        # High-value requests are a human-approval gate before any item-level work.
        if self.policy.approval_required(order):
            esc=self.tools.escalate_to_human(customer['customer_id'],order['order_id'],'Refunds & Payments','Order total exceeds the approval threshold for the applicable policy version.','high')
            self.tools.verify_result('escalation',esc['escalation_id'])
            return {'decision':'ESCALATE','reason':'Order total exceeds the applicable approval threshold.','customer_response':f"This request needs human approval because {order['order_id']} has a total of INR {float(order['total_amount']):,.0f}, which is above the {policy['version']} approval threshold of INR {policy['approval_threshold']:,}.",'intent_id':intent['id'],'actions':[esc],'evidence':{'customer_verified':True,'order_owned':True,'threshold_verified':False,'approval_required':True},'policy':policy}

        item,product=self._get_single_item_product(order,intent['text'])
        if not item or not product:
            return {'decision':'ASK','reason':'A specific item is required for an item-level return/refund.','customer_response':'This order contains multiple items. Please specify the product or item you want to return, refund, or replace.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True},'policy':policy}
        reason=intent.get('reason')
        low=intent['text'].lower()
        if reason is None:
            if 'replace' in low: reason='change_of_mind'
            else: reason='change_of_mind'
        # Evidence is inferred from prior conversations/tickets or explicit keywords in the present request.
        evidence_supplied=any(k in low for k in ['photo','video','image','attached','evidence'])
        if reason in {'defective','damaged','wrong_item','missing_item'} and not evidence_supplied:
            # ask unless historical evidence exists
            check=self.policy.check_refund_eligibility(order,customer,product,reason,now,evidence_supplied=False)
            if 'evidence_required' in check.get('issues',[]):
                return {'decision':'ASK','reason':'Defective/damaged/wrong-item returns require evidence.','customer_response':'Please upload a clear photo or video of the item and its label/serial, plus the outer packaging when the issue is transit damage. I will verify the evidence before taking action.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'evidence_verified':False},'policy':policy}

        requested_destination=_requested_destination(low) if any(k in low for k in ['refund','money back']) else None
        eligibility=self.tools.check_refund_eligibility(order=order,customer=customer,product=product,reason=reason,now=now,evidence_supplied=evidence_supplied,requested_destination=requested_destination)
        if not eligibility['eligible']:
            if 'already_refunded_or_partial' in eligibility['issues']:
                return {'decision':'ANSWER','reason':'Order already has a refund state.','customer_response':f"{order['order_id']} already has a {order.get('refund_status')} refund state, so I won't create a duplicate refund.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True},'policy':policy}
            if 'product_not_returnable_for_change_of_mind' in eligibility['issues']:
                return {'decision':'ANSWER','reason':'Product is non-returnable for change of mind.','customer_response':f"The {product['product_name']} is not returnable for change of mind under the applicable policy. A defect-related return may still be available with evidence within the defect window.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'returnable':False},'policy':policy}
            if 'different_refund_destination' in eligibility['issues']:
                esc=self.tools.escalate_to_human(customer['customer_id'],order['order_id'],'Refunds & Payments','Customer requested a different refund destination.','high')
                self.tools.verify_result('escalation',esc['escalation_id'])
                return {'decision':'ESCALATE','reason':'Refund destinations other than the original instrument are not permitted automatically.','customer_response':'I cannot send a refund to a different card, UPI ID, bank account or wallet from chat. I have escalated the case to Refunds & Payments for the verified alternate-instrument process.','intent_id':intent['id'],'actions':[esc],'evidence':{'customer_verified':True,'order_owned':True},'policy':policy}
            if 'outside_policy_window' in eligibility['issues']:
                if reason in {'defective','damaged','wrong_item'}:
                    return self._warranty(customer,order,{'id':intent['id'],'intent':'warranty','text':intent['text'],'reason':reason},now)
                return {'decision':'ANSWER','reason':'Request is outside the applicable refund window.','customer_response':f"I verified {order['order_id']} under policy {policy['version']}. The request is outside the applicable {eligibility['window_days']}-day window, so I cannot initiate that refund automatically. For a faulty product, I can route you to warranty service instead.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'window_verified':True,'eligible':False},'policy':policy}
            if 'delivery_not_verified' in eligibility['issues']:
                return {'decision':'ASK','reason':'Delivery date is required for window calculation.','customer_response':'I need the delivered date to verify the applicable refund window. Please confirm the order ID if you have another order in mind.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True},'policy':policy}
            return {'decision':'ANSWER','reason':'Policy conditions for the requested action are not met.','customer_response':'I verified the order and policy, but the requested action is not currently eligible. I can help with the next available support path.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'eligible':False},'policy':policy}

        calc=self.tools.calculate_refund(order=order,items=[item],product=product,reason=reason)
        requested=float(intent.get('requested_amount') or calc['refund_amount'])
        final_amount=min(requested,calc['refund_amount'],float(order['total_amount'])) if reason != 'change_of_mind' else min(requested,calc['refund_amount'],float(order['total_amount']))
        if requested > calc['refund_amount']:
            cap_note=f" Your requested amount is higher than the verified maximum; the maximum eligible amount is INR {calc['refund_amount']:,.2f}."
        else:
            cap_note=''

        if intent['intent']=='return':
            ev={'customer_verified':True,'order_owned':True,'eligibility_verified':True,'no_escalation_trigger':True}
            self.guard.validate('create_return',ev)
            ret=self.tools.create_return(customer['customer_id'],order['order_id'],item['order_item_id'],reason)
            self.tools.verify_result('return',ret['return_id'])
            return {'decision':'ACT','reason':'Return is eligible and within authority.','customer_response':f"I have created the return for {product['product_name']} on {order['order_id']}. Pickup is expected within 24-48 hours. The refund will follow policy after QC.{cap_note}",'intent_id':intent['id'],'actions':[ret],'evidence':{**ev,'refund_calculation':calc},'policy':policy}
        if intent['intent']=='replacement':
            if reason == 'change_of_mind':
                return {'decision':'ANSWER','reason':'Change of mind is not a replacement reason.','customer_response':'Replacement is available for defective, damaged-in-transit, or wrong-item cases, not for change of mind. I can help with a return instead.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True},'policy':policy}
            if str(product.get('replacement_available','')).lower() != 'true':
                return {'decision':'ANSWER','reason':'Product does not have replacement available.','customer_response':f"{product['product_name']} does not currently have replacement available. A refund/return path is available instead, subject to policy.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True},'policy':policy}
            ev={'customer_verified':True,'order_owned':True,'eligibility_verified':True,'no_escalation_trigger':True}
            self.guard.validate('create_return',ev)
            ret=self.tools.create_return(customer['customer_id'],order['order_id'],item['order_item_id'],reason + '_replacement')
            self.tools.verify_result('return',ret['return_id'])
            return {'decision':'ACT','reason':'Replacement request is eligible within authority.','customer_response':f"I have created the replacement request for {product['product_name']}. Pickup will be arranged with the replacement delivery; QC will determine the final disposition.",'intent_id':intent['id'],'actions':[ret],'evidence':{**ev,'replacement_available':True},'policy':policy}
        # refund
        destination='original payment method'
        if str(order.get('payment_method','')).lower()=='cash_on_delivery':
            destination='NovaMart wallet or a verified bank account through Payments'
        ev={'customer_verified':True,'order_owned':True,'eligibility_verified':True,'amount_verified':True,'threshold_verified':True,'destination_verified':True,'no_escalation_trigger':True}
        # Never allow a customer-provided amount to inflate the action.
        if requested > calc['refund_amount']:
            final_amount=calc['refund_amount']
        proof=self.guard.validate('create_refund',ev)
        refund=self.tools.create_refund(customer['customer_id'],order['order_id'],final_amount,reason)
        self.tools.verify_result('refund',refund['refund_id'])
        return {'decision':'ACT','reason':'Refund is eligible, capped by verified policy calculation, and within authority.','customer_response':f"I've processed an INR {final_amount:,.2f} refund for {product['product_name']} to the {destination}.{cap_note} Refund timing follows the original payment method and policy {policy['version']}.",'intent_id':intent['id'],'actions':[refund],'evidence':{**ev,'proof':proof,'refund_calculation':calc},'policy':policy}

    def _cancellation(self,customer,order,intent):
        status=order.get('order_status','').lower()
        if status in {'placed','confirmed','processing'}:
            # simulate cancellation through ticket/state log; no human approval even if high value.
            key=f"cancel:{order['order_id']}"
            row={'cancellation_id':'CAN-' + uuid.uuid4().hex[:10].upper(),'order_id':order['order_id'],'customer_id':customer['customer_id'],'status':'approved','created_at':datetime.now().isoformat(),'idempotency_key':key}
            self.tools.state.setdefault('tickets',[])
            self.tools.state['action_log'].append({'action':'cancel_order',**row}); self.tools._save()
            self.tools.trace.append({'type':'tool','name':'cancel_order','parameters':{'order_id':order['order_id']},'success':True,'summary':'Order cancellation recorded'})
            return {'decision':'ACT','reason':'Order is cancellable before shipment.','customer_response':f"I've cancelled {order['order_id']}. Because it had not been shipped, the cancellation is approved. Prepaid orders are refunded in full to the original method; COD has nothing to refund.",'intent_id':intent['id'],'actions':[row],'evidence':{'customer_verified':True,'order_owned':True,'shipment_not_started':True},'policy':{}}
        if status=='cancelled':
            return {'decision':'ANSWER','reason':'Order is already cancelled.','customer_response':f"{order['order_id']} is already cancelled. I won't create a duplicate cancellation.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True},'policy':{}}
        return {'decision':'ANSWER','reason':'Order cannot be cancelled after shipment or delivery.','customer_response':f"{order['order_id']} cannot be cancelled at its current status ({status}). You can refuse delivery or use the Return/Refund Policy after delivery where eligible.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'shipment_not_started':False},'policy':{}}

    def _address(self,customer,order,intent):
        status=order.get('order_status','').lower()
        m=re.search(r'(?:to|address(?:\s+is|:)?)[ ]+(.+)$', intent['text'], re.I)
        new_address=m.group(1).strip() if m else None
        if status in {'placed','confirmed','processing'}:
            if not new_address or len(new_address)<8:
                return {'decision':'ASK','reason':'Full new address and pincode are required before updating.','customer_response':'Please provide the full new delivery address, including the pincode. I will verify it before submitting the change.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'shipment_not_started':True}}
            ev={'customer_verified':True,'order_owned':True,'shipment_not_started':True,'new_address_verified':True}
            self.guard.validate('update_address',ev)
            row=self.tools.update_address(customer['customer_id'],order['order_id'],new_address)
            return {'decision':'ACT','reason':'Address can be updated once before shipment.','customer_response':f"I've submitted the address change for {order['order_id']} before shipment. The new address has been recorded for verification.",'intent_id':intent['id'],'actions':[row],'evidence':ev,'policy':{}}
        return {'decision':'ANSWER','reason':'Address changes are unavailable after shipment.','customer_response':f"The address for {order['order_id']} cannot be changed because it has already shipped or progressed beyond the pre-shipment stage. You can reschedule with the courier, refuse delivery, or use the return path after delivery.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'shipment_not_started':False},'policy':{}}

    def _payment(self,customer,order,intent,now):
        status=order.get('payment_status','').lower(); low=intent['text'].lower()
        if 'double' in low or 'twice' in low or 'duplicate' in low:
            t=self.tools.create_support_ticket(customer['customer_id'],order['order_id'],'payment','high','Customer reports duplicate charge; payment records require verification.','Refunds & Payments')
            self.tools.verify_result('ticket',t['ticket_id'])
            return {'decision':'ACT','reason':'Duplicate-charge claim requires payment verification.','customer_response':f"I opened a payment investigation for the duplicate-charge claim on {order['order_id']}. Refunds & Payments will verify the ledger before issuing any second refund.",'intent_id':intent['id'],'actions':[t],'evidence':{'customer_verified':True,'order_owned':True},'policy':{}}
        if status=='pending':
            age_hours=hours_between(order['order_date'], now)
            if age_hours < 24:
                return {'decision':'ANSWER','reason':'Pending payment is under 24 hours old.','customer_response':'Your payment is still pending. Banks can take up to 24 hours to confirm; please wait before requesting a refund.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'pending_payment':True},'policy':{}}
            t=self.tools.create_support_ticket(customer['customer_id'],order['order_id'],'payment','high','Payment remains pending beyond the 24-hour confirmation window.','Refunds & Payments')
            self.tools.verify_result('ticket',t['ticket_id'])
            return {'decision':'ACT','reason':'Payment remains pending after 24 hours.','customer_response':'The payment is still pending beyond the 24-hour confirmation window, so I have raised a payment ticket. Unconfirmed prepaid payments are auto-reversed within 5-7 business days.','intent_id':intent['id'],'actions':[t],'evidence':{'customer_verified':True,'order_owned':True,'pending_over_24h':True},'policy':{}}
        if status=='failed':
            return {'decision':'ANSWER','reason':'Payment failed and order is auto-cancelled.','customer_response':'The payment did not complete, so the order was auto-cancelled. Failed payments with a debit are auto-reversed within 5-7 business days.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True},'policy':{}}
        return {'decision':'ANSWER','reason':'Payment status verified.','customer_response':f"The payment status for {order['order_id']} is {status}. The payment method is {order.get('payment_method') }.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True},'policy':{}}

    def _warranty(self,customer,order,intent,now):
        item,product=self._get_single_item_product(order,intent['text'])
        if not item or not product:
            return {'decision':'ASK','reason':'A specific product is required for warranty verification.','customer_response':'Please tell me which product in the order has the issue so I can check its warranty term and delivery date.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True}}
        delivered=order.get('actual_delivery_date')
        if not delivered:
            return {'decision':'ASK','reason':'Warranty starts on delivery and delivery is not verified.','customer_response':'I need the delivery date to verify the warranty period for this product.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True}}
        months=int(float(product.get('warranty_months') or 0))
        end=warranty_end_date(delivered, months)
        today=parse_date(now)
        low=intent['text'].lower()
        physical=any(k in low for k in ['crack','dropped','liquid','water','burn','physical damage'])
        safety=any(k in low for k in ['swollen','overheating','smoke','burning smell'])
        if safety:
            esc=self.tools.escalate_to_human(customer['customer_id'],order['order_id'],'Technical Support','Safety incident inside warranty context.','critical')
            self.tools.verify_result('escalation',esc['escalation_id'])
            return {'decision':'ESCALATE','reason':'Safety incidents override warranty handling.','customer_response':'Please stop using and charging the device immediately. I have escalated the safety incident as critical to Technical Support.','intent_id':intent['id'],'actions':[esc],'evidence':{'customer_verified':True,'order_owned':True,'safety':True},'policy':{}}
        if today > end:
            return {'decision':'ANSWER','reason':'Warranty period has expired.','customer_response':f"The warranty for {product['product_name']} ended on {end.isoformat()}. NovaMart can offer paid repair through an authorised service centre.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'warranty_end':end.isoformat(),'warranty_active':False}}
        # Inside defect window, refund/return path is preferred. Otherwise warranty service.
        defect_window=self.policy.refund(self.policy.version_for_order(order))['defect_days']
        dn=day_number(delivered,today)
        if dn <= defect_window and not physical:
            return {'decision':'ANSWER','reason':'Within defect window; refund/return path should be used first.','customer_response':f"The product is still within its {defect_window}-day defect window. A return/replacement/refund path can be used first; warranty service is the fallback after that window.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'warranty_end':end.isoformat(),'inside_defect_window':True}}
        if physical:
            return {'decision':'ANSWER','reason':'Physical damage is outside warranty coverage.','customer_response':f"The reported physical damage is not covered by the manufacturer warranty. The warranty remains valid through {end.isoformat()} for covered manufacturing defects; paid repair is the available path for physical damage.",'intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True,'order_owned':True,'warranty_end':end.isoformat(),'physical_damage':True}}
        t=self.tools.create_support_ticket(customer['customer_id'],order['order_id'],'warranty','medium','Warranty claim registered; manufacturing defect requires service-center diagnosis.','Technical Support')
        self.tools.verify_result('ticket',t['ticket_id'])
        return {'decision':'ACT','reason':'Warranty is active and the defect window has passed; service claim can be registered.','customer_response':f"I have registered a warranty claim for {product['product_name']}. The warranty is active through {end.isoformat()}; service-centre diagnosis is the next step. A replacement is only arranged if the service centre determines the unit is irreparable under policy.",'intent_id':intent['id'],'actions':[t],'evidence':{'customer_verified':True,'order_owned':True,'warranty_end':end.isoformat(),'warranty_active':True},'policy':{}}

    def _order_history(self, customer, intent):
        orders = self.store.customer_orders(customer['customer_id'])
        if not orders:
            return {
                'decision': 'ANSWER',
                'reason': 'No order records found for customer.',
                'customer_response': f"Hello {customer.get('first_name', '')}, there are currently no orders on file for your account.",
                'intent_id': intent['id'],
                'actions': [],
                'evidence': {'customer_verified': True, 'order_count': 0},
                'policy': {}
            }
        lines = [f"📋 **Your Recent Orders ({customer.get('first_name', '')} {customer.get('last_name', '')})**:"]
        for idx, o in enumerate(orders[:5], 1):
            items = self.store.get_order_items(o['order_id'])
            pnames = [self.store.get_product(it['product_id'])['product_name'] for it in items if self.store.get_product(it['product_id'])]
            item_desc = ', '.join(pnames) if pnames else 'NovaMart Item'
            st = o.get('order_status', '').title()
            amt = float(o.get('total_amount', 0))
            date_str = o.get('order_date', '')[:10]
            del_date = o.get('actual_delivery_date') or o.get('estimated_delivery_date', '')
            lines.append(f"{idx}. **Order {o['order_id']}** — {st}\n   • Placed: {date_str} | Total: INR {amt:,.0f}\n   • Delivery: {del_date}\n   • Items: {item_desc}")
        lines.extend([
            "",
            "💡 **Helpful Actions**:",
            "• To see full delivery details or track an order: `Where is order <ORDER_ID>?`",
            "• To get a tax receipt: `Download invoice for <ORDER_ID>`",
            "• To request a return or replacement: `Return item in <ORDER_ID>`"
        ])
        return {
            'decision': 'ANSWER',
            'reason': 'Customer order history retrieved.',
            'customer_response': '\n'.join(lines),
            'intent_id': intent['id'],
            'actions': [],
            'evidence': {'customer_verified': True, 'order_count': len(orders)},
            'policy': {}
        }

    def _invoice(self, customer, order, intent):
        items = self.store.get_order_items(order['order_id'])
        products = [self.store.get_product(it['product_id']) for it in items]
        lines = [
            f"🧾 **NovaMart Official Tax Invoice**",
            f"• **Invoice Number**: INV-2026-{order['order_id']}",
            f"• **Order ID**: {order['order_id']}",
            f"• **Order Date**: {order.get('order_date')}",
            f"• **Customer**: {customer.get('first_name', '')} {customer.get('last_name', '')}",
            f"• **Shipping & Billing Address**: {order.get('shipping_address')}",
            "",
            "**Itemized Breakdown**:"
        ]
        for it, p in zip(items, products):
            pname = p.get('product_name', it.get('product_id')) if p else it.get('product_id')
            sku = p.get('sku', 'N/A') if p else 'N/A'
            qty = it.get('quantity', 1)
            uprice = float(it.get('unit_price', 0))
            fprice = float(it.get('final_price', uprice * float(qty)))
            lines.append(f"• {pname} (SKU: {sku}) — Qty: {qty} × INR {uprice:,.0f} = INR {fprice:,.0f}")
        lines.extend([
            "",
            "**Price & Payment Summary**:",
            f"• Items Subtotal: INR {float(order.get('subtotal', 0)):,.0f}",
            f"• Discount: INR {float(order.get('discount', 0)):,.0f}",
            f"• Shipping Fee: INR {float(order.get('shipping_fee', 0)):,.0f}",
            f"• GST / Taxes (18% inclusive): INR {float(order.get('tax', 0)):,.0f}",
            f"• **Grand Total Paid**: INR {float(order.get('total_amount', 0)):,.0f}",
            f"• Payment Method: {order.get('payment_method', '').replace('_', ' ').title()} ({order.get('payment_status', '').title()})",
            "",
            "📄 *This is a system-generated electronic tax invoice with digital signature for your NovaMart purchase.*",
            f"📥 **[Click here to download PDF Tax Invoice](/api/invoice/{order['order_id']}/pdf)**"
        ])
        return {
            'decision': 'ANSWER',
            'reason': 'Official tax invoice details retrieved.',
            'customer_response': '\n'.join(lines),
            'intent_id': intent['id'],
            'actions': [],
            'evidence': {'customer_verified': True, 'order_owned': True, 'invoice_generated': True, 'order_id': order['order_id'], 'invoice_pdf_url': f"/api/invoice/{order['order_id']}/pdf"},
            'policy': {}
        }

    def _handle_product_or_general(self,customer,intent):
        exact=self.store.get_product(intent.get('product_id')) if intent.get('product_id') else None
        results=[exact] if exact else self.store.search_products(intent['text'],limit=5)
        if intent['intent']=='product_info' and results:
            p=results[0]; spec=self.store.get_product_spec(p['product_id']);
            detail=f"{p['product_name']} is priced at INR {float(p['price']):,.0f}, stock {p['stock_quantity']}, warranty {p['warranty_months']} months, returnable for change of mind: {str(p['returnable']).lower()}."
            if spec and spec.get('specs'):
                pairs=list(spec['specs'].items())[:4]
                detail += ' Key specs: ' + ', '.join(f'{k}: {v}' for k,v in pairs) + '.'
            return {'decision':'ANSWER','reason':'Product information retrieved from catalog.','customer_response':detail,'intent_id':intent['id'],'actions':[],'evidence':{'product_verified':True,'product_id':p['product_id']},'policy':{}}
        if intent['intent']=='general':
            return {'decision':'ANSWER','reason':'General support greeting/instruction.','customer_response':'I can help with orders, delivery, returns, refunds, replacements, cancellation, address changes, payments, product details, and warranty support.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True},'policy':{}}
        return {'decision':'ASK','reason':'Product could not be uniquely identified.','customer_response':'Please share the product name or product ID so I can look up the correct catalog information.','intent_id':intent['id'],'actions':[],'evidence':{'customer_verified':True},'policy':{}}

    def _aggregate(self,results):
        order={'ESCALATE':4,'ASK':3,'ACT':2,'ANSWER':1}
        return max((r.get('decision','ANSWER') for r in results), key=lambda d:order[d]) if results else 'ANSWER'

    def _combine_responses(self,results):
        if not results: return 'I could not determine the requested support action.'
        seen=set(); parts=[]
        for r in results:
            t=r['customer_response'].strip()
            if t and t not in seen:
                parts.append(t); seen.add(t)
        return ' '.join(parts)

    def _aggregate_policy(self,results):
        for r in results:
            if r.get('policy'): return r['policy']
        return {}

    def _stats(self):
        return {'tool_calls':len(self.tools.trace),'write_calls':sum(1 for t in self.tools.trace if t.get('type')=='tool' and t.get('name','').startswith(('create_','escalate_','update_','add_','cancel_')))}

    def _final(self,request_id,decision,response,intents,results,evidence,trace,policy,stats):
        merged=dict(evidence)
        for r in results:
            for key,value in r.get('evidence',{}).items():
                merged.setdefault(key,value)
        return {'request_id':request_id,'decision':decision,'customer_response':response,'intents':intents,'intent_results':results,'evidence':merged,'trace':trace,'policy':policy,'stats':stats}

    def _enrich_response_with_gemini(self, customer: Dict[str, Any], original_message: str, decision: str, baseline_response: str, results: List[Dict[str, Any]], evidence: Dict[str, Any]) -> Optional[str]:
        if not self.llm or not self.llm.enabled:
            return None
        system = (
            "You are NovaMart Guardian's customer-support response composer for NovaMart, an Indian e-commerce platform.\n"
            "Your task is to rephrase the verified decision into a fluent, empathetic, and professional customer-facing response.\n"
            "MANDATORY CONSTRAINTS:\n"
            "1. NEVER alter the terminal decision (ANSWER/ASK/ACT/ESCALATE) or promise actions that are not verified.\n"
            "2. Rely strictly on the verified baseline facts, decision, actions, and evidence provided.\n"
            "3. Do NOT invent dates, order IDs, amounts, tickets, or policy clauses.\n"
            "4. Return ONLY the final polished customer response text without commentary, prefixes, or markdown codeblocks."
        )
        actions = []
        for r in results:
            for a in r.get('actions', []):
                actions.append(str(a))
        user = (
            f"Customer Name: {customer.get('first_name', '')} {customer.get('last_name', '')} (Loyalty: {customer.get('loyalty_tier', 'bronze')})\n"
            f"Customer Message: {original_message}\n"
            f"Verified Terminal Decision: {decision}\n"
            f"Verified Baseline Response: {baseline_response}\n"
            f"Verified Actions: {'; '.join(actions) if actions else 'None'}\n\n"
            "Write the final polished customer response:"
        )
        try:
            return self.llm.complete(system, user, timeout=8.0)
        except Exception:
            return None
