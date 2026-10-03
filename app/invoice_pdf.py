from __future__ import annotations
import io
from typing import Any, Dict, List
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_invoice_pdf(order: Dict[str, Any], customer: Dict[str, Any], items: List[Dict[str, Any]], products: List[Dict[str, Any]]) -> bytes:
    """Generates an official GST-compliant tax invoice PDF for a NovaMart order."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CompTitle', parent=styles['Heading1'], fontSize=15, leading=17, textColor=colors.HexColor('#1a1a24'))
    inv_title_style = ParagraphStyle('InvTitle', parent=styles['Heading2'], fontSize=11, leading=13, alignment=1, textColor=colors.HexColor('#ef242b'))
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=8.5, leading=11.5, textColor=colors.HexColor('#4a4a5a'))
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=8.5, leading=11.5, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a1a24'))
    total_style = ParagraphStyle('TotalStyle', parent=styles['Normal'], fontSize=10, leading=13, fontName='Helvetica-Bold', textColor=colors.HexColor('#ef242b'))
    
    elements = []
    
    # Header Banner
    elements.append(Paragraph("<b>NOVAMART RETAIL PRIVATE LIMITED</b>", title_style))
    elements.append(Paragraph(
        "GSTIN: 27AABCN1234F1Z5 &nbsp;|&nbsp; CIN: U52100MH2024PTC123456 &nbsp;|&nbsp; PAN: AABCN1234F<br/>"
        "Registered Office: NovaMart Campus, Outer Ring Road, Bengaluru, Karnataka - 560103<br/>"
        "Website: www.novamart.in &nbsp;|&nbsp; Support: support@novamart.in",
        meta_style
    ))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#ef242b'), spaceBefore=2, spaceAfter=8))
    
    # Document Title
    elements.append(Paragraph("<b>TAX INVOICE / BILL OF SUPPLY &nbsp;(ORIGINAL FOR RECIPIENT)</b>", inv_title_style))
    elements.append(Spacer(1, 8))
    
    # Meta / Address Grid
    order_id = order.get('order_id', 'N/A')
    order_date = order.get('order_date', 'N/A')
    pay_method = str(order.get('payment_method', 'N/A')).replace('_', ' ').title()
    pay_status = str(order.get('payment_status', 'N/A')).title()
    courier = order.get('courier') or 'NovaMart Swift Courier'
    tracking = order.get('tracking_number') or 'TRK-' + order_id
    cust_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or 'Valued Customer'
    shipping_addr = order.get('shipping_address') or 'Customer Address'
    state = order.get('state') or 'India'
    
    info_data = [
        [
            Paragraph(
                f"<b>Invoice No:</b> INV-2026-{order_id}<br/>"
                f"<b>Invoice Date:</b> {order_date}<br/>"
                f"<b>Order ID:</b> {order_id}<br/>"
                f"<b>Payment Mode:</b> {pay_method} ({pay_status})<br/>"
                f"<b>Logistics Partner:</b> {courier}<br/>"
                f"<b>AWB / Tracking No:</b> {tracking}",
                meta_style
            ),
            Paragraph(
                f"<b>Billed To &amp; Shipped To:</b><br/>"
                f"<b>{cust_name}</b> (Tier: {str(customer.get('loyalty_tier', 'bronze')).upper()})<br/>"
                f"{shipping_addr}<br/>"
                f"<b>Place of Supply:</b> {state} (State Code: 29)<br/>"
                f"<b>Customer ID:</b> {customer.get('customer_id', 'N/A')}",
                meta_style
            )
        ]
    ]
    info_table = Table(info_data, colWidths=[260, 260])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#d9dce5')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e5ee')),
        ('PADDING', (0,0), (-1,-1), 7),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 12))
    
    # Items Table
    headers = [
        Paragraph("<b>#</b>", bold_style),
        Paragraph("<b>Product Description</b>", bold_style),
        Paragraph("<b>SKU / Code</b>", bold_style),
        Paragraph("<b>Qty</b>", bold_style),
        Paragraph("<b>Rate (₹)</b>", bold_style),
        Paragraph("<b>Tax (18% ₹)</b>", bold_style),
        Paragraph("<b>Net Total (₹)</b>", bold_style),
    ]
    table_data = [headers]
    
    for idx, (it, p) in enumerate(zip(items, products), 1):
        pname = p.get('product_name', it.get('product_id')) if p else it.get('product_id')
        sku = p.get('sku', 'NOV-' + str(it.get('product_id', 'ITEM'))) if p else 'NOV-ITEM'
        qty = int(float(it.get('quantity', 1)))
        uprice = float(it.get('unit_price', 0))
        fprice = float(it.get('final_price', uprice * qty))
        tax_part = round(fprice * 0.18 / 1.18, 2)
        
        table_data.append([
            Paragraph(str(idx), meta_style),
            Paragraph(pname, meta_style),
            Paragraph(sku, meta_style),
            Paragraph(str(qty), meta_style),
            Paragraph(f"{uprice:,.2f}", meta_style),
            Paragraph(f"{tax_part:,.2f}", meta_style),
            Paragraph(f"{fprice:,.2f}", meta_style),
        ])
        
    subtotal = float(order.get('subtotal', 0))
    discount = float(order.get('discount', 0))
    shipping = float(order.get('shipping_fee', 0))
    tax = float(order.get('tax', 0))
    total = float(order.get('total_amount', 0))
    
    # Totals Rows
    table_data.append(['', '', '', '', '', Paragraph("<b>Items Subtotal:</b>", meta_style), Paragraph(f"₹{subtotal:,.2f}", meta_style)])
    if discount > 0:
        table_data.append(['', '', '', '', '', Paragraph("<b>Promo Discount:</b>", meta_style), Paragraph(f"-₹{discount:,.2f}", meta_style)])
    table_data.append(['', '', '', '', '', Paragraph("<b>Delivery / Shipping:</b>", meta_style), Paragraph(f"₹{shipping:,.2f}", meta_style)])
    table_data.append(['', '', '', '', '', Paragraph("<b>GST (18% Incl):</b>", meta_style), Paragraph(f"₹{tax:,.2f}", meta_style)])
    table_data.append(['', '', '', '', '', Paragraph("<b>Grand Total:</b>", total_style), Paragraph(f"<b>₹{total:,.2f}</b>", total_style)])
    
    items_table = Table(table_data, colWidths=[20, 185, 95, 30, 60, 60, 70])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#eceef5')),
        ('LINEBELOW', (0,0), (-1,0), 1.2, colors.HexColor('#c3c7d6')),
        ('LINEBELOW', (0,1), (-1,-1), 0.5, colors.HexColor('#e8eaf2')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 14))
    
    # Legal Footer & Verification Note
    footer_data = [
        [
            Paragraph(
                "<b>Policy & Return Conditions:</b><br/>"
                "• All eligible items can be returned or replaced within the applicable policy window from delivery.<br/>"
                "• Products with manufacturer warranty are eligible for authorized brand service support.<br/>"
                "• This invoice is an authorized digital electronic tax memorandum valid under Section 31 of CGST Act.",
                meta_style
            ),
            Paragraph(
                "<b>For NovaMart Retail Private Limited</b><br/><br/>"
                "<font color='#2ecc71'>✔ <b>DIGITALLY VERIFIED SIGNATURE</b></font><br/>"
                "Finance &amp; Compliance Cell<br/>"
                "<i>Electronic Verification Token: NV-AUTH-OK</i>",
                meta_style
            )
        ]
    ]
    footer_table = Table(footer_data, colWidths=[340, 180])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(footer_table)
    
    doc.build(elements)
    return buffer.getvalue()
