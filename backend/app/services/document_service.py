import io
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import qrcode
import qrcode.image.svg

from app.models.tenant import Organization
from app.models.crm import ClientSale, ClientAccount
from app.models.procurement import PurchaseOrder, ShipmentTracking

class DocumentService:
    @staticmethod
    def generate_qr_code_svg(data_url: str, box_size: int = 10) -> str:
        """
        Generates a crisp inline SVG QR code for scannable payment or telemetry links.
        """
        factory = qrcode.image.svg.SvgPathImage
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=2,
            image_factory=factory
        )
        qr.add_data(data_url)
        qr.make(fit=True)
        img = qr.make_image()
        stream = io.BytesIO()
        img.save(stream)
        raw_svg = stream.getvalue().decode("utf-8")
        # Strip XML declaration if present so it embeds cleanly in HTML
        cleaned_svg = re.sub(r"<\?xml.*?\?>", "", raw_svg).strip()
        return cleaned_svg

    @classmethod
    def render_invoice_html(
        cls,
        sale: ClientSale,
        org: Optional[Organization] = None,
        base_url: str = "https://therealbonz.com/JsProject",
        auto_print: bool = False
    ) -> str:
        base_url = base_url.rstrip("/")
        brand_name = (org.brand_name or org.name) if org else "Order Bot Distribution"
        brand_color = (org.brand_accent_color or "#4f46e5") if org else "#4f46e5"
        logo_url = org.brand_logo_url if org else None
        support_email = (org.support_email or "billing@therealbonz.com") if org else "billing@therealbonz.com"
        support_phone = (org.support_phone or "+1 (800) 555-0199") if org else "+1 (800) 555-0199"
        custom_footer = (org.custom_footer_text or "Thank you for your business. Certified B2B Distribution.") if org else "Thank you for your business."

        client_name = sale.client.account_name if sale.client else "Valued Client"
        contact_name = "Accounts Payable / Procurement"
        contact_email = sale.customer_email or (sale.client.primary_contact.email if sale.client and sale.client.primary_contact else "purchasing@client.com")
        contact_phone = sale.customer_phone or (sale.client.primary_contact.phone if sale.client and sale.client.primary_contact else "")

        sale_date_str = sale.sale_date.strftime("%B %d, %Y") if sale.sale_date else datetime.now(timezone.utc).strftime("%B %d, %Y")
        
        # Payment Link / QR Code
        is_paid = str(sale.payment_status).lower() == "paid"
        if is_paid:
            qr_target_url = f"{base_url}/track/{sale.order_number}"
            qr_label = "Payment Verified • Scan for Delivery Telemetry"
            status_badge = '<span class="badge paid"><i class="fa-solid fa-circle-check"></i> PAID IN FULL</span>'
            balance_due = 0.00
        else:
            session_id = sale.stripe_session_id or f"cs_inv_{sale.id[:12]}"
            qr_target_url = f"{base_url}/checkout/pay/{session_id}"
            qr_label = "Scan to Pay Securely via Stripe • 256-Bit SSL"
            status_badge = '<span class="badge unpaid"><i class="fa-solid fa-clock"></i> PAYMENT DUE (NET 30)</span>'
            balance_due = sale.amount

        qr_svg = cls.generate_qr_code_svg(qr_target_url)

        # Parse line items summary into structured table rows
        items_html = ""
        raw_items = sale.items_summary.split(",") if "," in sale.items_summary else [sale.items_summary]
        subtotal = sale.amount
        for idx, item in enumerate(raw_items, 1):
            clean_item = item.strip()
            qty = 1
            desc = clean_item
            match = re.match(r"^(\d+)[xX]?\s*(.*)$", clean_item)
            if match:
                qty = int(match.group(1))
                desc = match.group(2).strip()
            unit_price = round(subtotal / len(raw_items) / (qty if qty > 0 else 1), 2)
            line_total = round(unit_price * qty, 2)
            items_html += f"""
            <tr>
                <td class="text-center font-mono">{idx:02d}</td>
                <td class="font-medium">
                    <div class="item-name">{desc}</div>
                    <div class="item-sub">SKU: DISTRO-{1000 + idx} &bull; Standard Wholesale Unit</div>
                </td>
                <td class="text-center font-mono font-bold">{qty}</td>
                <td class="text-right font-mono">${unit_price:,.2f}</td>
                <td class="text-right font-mono font-bold">${line_total:,.2f}</td>
            </tr>
            """

        logo_header = f'<img src="{logo_url}" alt="{brand_name}" class="brand-logo" />' if logo_url else f'<div class="brand-title">{brand_name}</div>'
        auto_print_js = '<script>window.onload = () => { setTimeout(() => window.print(), 350); };</script>' if auto_print else ""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Commercial Invoice #{sale.order_number} • {brand_name}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --brand-color: {brand_color};
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --bg-light: #f8fafc;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}
        body {{
            background-color: #f1f5f9;
            color: var(--text-main);
            padding: 30px 15px;
            font-size: 13px;
            line-height: 1.5;
        }}
        .print-toolbar {{
            max-width: 820px;
            margin: 0 auto 16px auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #ffffff;
            padding: 12px 20px;
            border-radius: 10px;
            border: 1px solid #cbd5e1;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        }}
        .invoice-sheet {{
            max-width: 820px;
            margin: 0 auto;
            background: #ffffff;
            padding: 44px;
            border-radius: 12px;
            border: 1px solid #cbd5e1;
            box-shadow: 0 10px 25px rgba(0,0,0,0.08);
            position: relative;
        }}
        .brand-logo {{
            max-height: 48px;
            max-width: 220px;
            object-fit: contain;
            margin-bottom: 8px;
        }}
        .brand-title {{
            font-size: 22px;
            font-weight: 800;
            color: var(--brand-color);
            letter-spacing: -0.5px;
        }}
        .doc-heading {{
            text-align: right;
        }}
        .doc-title {{
            font-size: 28px;
            font-weight: 900;
            letter-spacing: 1px;
            color: #1e293b;
            text-transform: uppercase;
        }}
        .doc-meta {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 9999px;
            font-weight: 800;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 8px;
        }}
        .badge.paid {{
            background: #ecfdf5;
            color: #047857;
            border: 1px solid #a7f3d0;
        }}
        .badge.unpaid {{
            background: #fffbeb;
            color: #b45309;
            border: 1px solid #fde68a;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-top: 32px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
        }}
        .meta-block h4 {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-muted);
            margin-bottom: 8px;
            font-weight: 700;
        }}
        .meta-block .name {{
            font-size: 15px;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 3px;
        }}
        .meta-block p {{
            font-size: 13px;
            color: #475569;
            line-height: 1.4;
        }}
        table.items-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 32px;
        }}
        table.items-table th {{
            background: #f8fafc;
            color: #475569;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.6px;
            font-weight: 700;
            padding: 12px 14px;
            border-top: 1px solid var(--border-color);
            border-bottom: 1px solid var(--border-color);
            text-align: left;
        }}
        table.items-table td {{
            padding: 14px;
            border-bottom: 1px solid #f1f5f9;
            font-size: 13px;
            vertical-align: top;
        }}
        .item-name {{
            font-weight: 600;
            color: #0f172a;
        }}
        .item-sub {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
        }}
        .financial-section {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-top: 28px;
            gap: 24px;
        }}
        .qr-box {{
            flex: 1;
            display: flex;
            align-items: center;
            gap: 16px;
            background: var(--bg-light);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            max-width: 440px;
        }}
        .qr-render svg {{
            width: 90px;
            height: 90px;
            display: block;
            border-radius: 6px;
            background: #ffffff;
            padding: 4px;
            border: 1px solid #e2e8f0;
        }}
        .qr-desc h5 {{
            font-size: 12px;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 4px;
        }}
        .qr-desc p {{
            font-size: 11px;
            color: var(--text-muted);
            line-height: 1.4;
            margin-bottom: 8px;
        }}
        .qr-desc a {{
            color: var(--brand-color);
            font-weight: 600;
            text-decoration: none;
            font-size: 11px;
        }}
        .totals-table {{
            width: 280px;
            border-collapse: collapse;
        }}
        .totals-table tr td {{
            padding: 6px 0;
            font-size: 13px;
        }}
        .totals-table tr.grand-total td {{
            padding-top: 10px;
            border-top: 2px solid #0f172a;
            font-size: 16px;
            font-weight: 800;
            color: #0f172a;
        }}
        .totals-table tr.due td {{
            color: var(--brand-color);
            font-weight: 800;
            font-size: 14px;
        }}
        .footer-note {{
            margin-top: 36px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            text-align: center;
            font-size: 11px;
            color: var(--text-muted);
            line-height: 1.6;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 12px;
            cursor: pointer;
            text-decoration: none;
            border: none;
            transition: 0.15s;
        }}
        .btn-primary {{
            background: var(--brand-color);
            color: #ffffff;
        }}
        .btn-secondary {{
            background: #f1f5f9;
            color: #334155;
            border: 1px solid #cbd5e1;
        }}
        .text-center {{ text-align: center; }}
        .text-right {{ text-align: right; }}
        .font-mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
        .font-bold {{ font-weight: 700; }}
        
        @media print {{
            body {{
                background: #ffffff !important;
                padding: 0 !important;
            }}
            .print-toolbar {{
                display: none !important;
            }}
            .invoice-sheet {{
                border: none !important;
                box-shadow: none !important;
                padding: 20px 0 !important;
                max-width: 100% !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="print-toolbar">
        <div>
            <span style="font-weight: 800; font-size: 14px;"><i class="fa-solid fa-file-invoice text-indigo-600"></i> Commercial Invoice Preview</span>
            <span style="color: #64748b; font-size: 12px; margin-left: 8px;">#{sale.order_number}</span>
        </div>
        <div style="display: flex; gap: 10px;">
            <button onclick="window.print()" class="btn btn-primary"><i class="fa-solid fa-print"></i> Print / Save PDF</button>
            <button onclick="window.close()" class="btn btn-secondary"><i class="fa-solid fa-xmark"></i> Close</button>
        </div>
    </div>

    <div class="invoice-sheet">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                {logo_header}
                <div style="color: #64748b; font-size: 12px; margin-top: 4px;">Commercial Distribution & Sourcing Network</div>
                <div style="color: #64748b; font-size: 12px;">{support_email} &bull; {support_phone}</div>
            </div>
            <div class="doc-heading">
                <div class="doc-title">INVOICE</div>
                <div class="doc-meta">Invoice No: <strong style="color: #0f172a; font-family: monospace;">INV-{sale.order_number}</strong></div>
                <div class="doc-meta">Issue Date: {sale_date_str}</div>
                <div class="doc-meta">Payment Terms: Net 30 Days</div>
                <div>{status_badge}</div>
            </div>
        </div>

        <div class="meta-grid">
            <div class="meta-block">
                <h4>Billed To (Client Account)</h4>
                <div class="name">{client_name}</div>
                <p>Attn: {contact_name}</p>
                <p>{contact_email} {('&bull; ' + contact_phone) if contact_phone else ''}</p>
                <p style="margin-top: 4px; font-size: 11px; color: #94a3b8;">Client Reference: #{sale.client_id[:8] if sale.client_id else 'Direct'}</p>
            </div>
            <div class="meta-block" style="text-align: right;">
                <h4>Remittance / Issuer</h4>
                <div class="name">{brand_name}</div>
                <p>Enterprise Fulfillment Logistics Dept</p>
                <p>Support: {support_email}</p>
                <p>Direct: {support_phone}</p>
            </div>
        </div>

        <table class="items-table">
            <thead>
                <tr>
                    <th style="width: 45px;" class="text-center">Item</th>
                    <th>Description & Specifications</th>
                    <th style="width: 70px;" class="text-center">Qty</th>
                    <th style="width: 120px;" class="text-right">Unit Price</th>
                    <th style="width: 130px;" class="text-right">Line Total</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>

        <div class="financial-section">
            <div class="qr-box">
                <div class="qr-render">
                    {qr_svg}
                </div>
                <div class="qr-desc">
                    <h5><i class="fa-solid fa-qrcode text-indigo-600"></i> Instant Mobile Payment & Telemetry</h5>
                    <p>{qr_label}</p>
                    <a href="{qr_target_url}" target="_blank">Direct Link &rarr;</a>
                </div>
            </div>

            <table class="totals-table">
                <tr>
                    <td style="color: #64748b;">Subtotal</td>
                    <td class="text-right font-mono font-bold">${subtotal:,.2f}</td>
                </tr>
                <tr>
                    <td style="color: #64748b;">Estimated Tax (0.0%)</td>
                    <td class="text-right font-mono">$0.00</td>
                </tr>
                <tr>
                    <td style="color: #64748b;">Freight / Logistics</td>
                    <td class="text-right font-mono" style="color: #059669; font-weight: 600;">FREE</td>
                </tr>
                <tr class="grand-total">
                    <td>Total Amount</td>
                    <td class="text-right font-mono">${subtotal:,.2f}</td>
                </tr>
                <tr class="due">
                    <td>Balance Outstanding</td>
                    <td class="text-right font-mono">${balance_due:,.2f}</td>
                </tr>
            </table>
        </div>

        <div class="footer-note">
            <p style="font-weight: 600; color: #475569;">{custom_footer}</p>
            <p style="margin-top: 3px;">Payment inquiries: <a href="mailto:{support_email}" style="color: {brand_color};">{support_email}</a> &bull; Certified Automated Commerce Network</p>
        </div>
    </div>
    {auto_print_js}
</body>
</html>"""

    @classmethod
    def render_packing_slip_html(
        cls,
        sale: ClientSale,
        org: Optional[Organization] = None,
        base_url: str = "https://therealbonz.com/JsProject",
        auto_print: bool = False
    ) -> str:
        base_url = base_url.rstrip("/")
        brand_name = (org.brand_name or org.name) if org else "Order Bot Distribution"
        brand_color = (org.brand_accent_color or "#4f46e5") if org else "#4f46e5"
        logo_url = org.brand_logo_url if org else None
        support_email = (org.support_email or "support@therealbonz.com") if org else "support@therealbonz.com"

        client_name = sale.client.account_name if sale.client else "Direct Commercial Account"
        contact_name = "Receiving Dock / Warehouse Team"

        pack_date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        tracking_url = f"{base_url}/track/{sale.order_number}"
        qr_svg = cls.generate_qr_code_svg(tracking_url)

        # Retrieve shipment / carrier info if available
        carrier_name = "Automated Freight Carrier"
        tracking_no = "PENDING ASSIGNMENT"
        if sale.purchase_orders:
            po = sale.purchase_orders[0]
            if po.shipments:
                carrier_name = po.shipments[0].carrier
                tracking_no = po.shipments[0].tracking_number

        # Parse pick list items
        items_html = ""
        raw_items = sale.items_summary.split(",") if "," in sale.items_summary else [sale.items_summary]
        total_units = 0
        for idx, item in enumerate(raw_items, 1):
            clean_item = item.strip()
            qty = 1
            desc = clean_item
            match = re.match(r"^(\d+)[xX]?\s*(.*)$", clean_item)
            if match:
                qty = int(match.group(1))
                desc = match.group(2).strip()
            total_units += qty
            items_html += f"""
            <tr>
                <td class="text-center"><div class="check-box"></div></td>
                <td class="text-center font-mono">{idx:02d}</td>
                <td>
                    <div class="font-bold text-dark">{desc}</div>
                    <div class="sub-text">SKU: PK-WH-{1000 + idx} &bull; Zone: B2-RACK-04</div>
                </td>
                <td class="text-center font-mono font-bold text-lg">{qty}</td>
                <td class="text-center font-mono" style="color: #64748b;">______</td>
            </tr>
            """

        logo_header = f'<img src="{logo_url}" alt="{brand_name}" class="brand-logo" />' if logo_url else f'<div class="brand-title">{brand_name}</div>'
        auto_print_js = '<script>window.onload = () => { setTimeout(() => window.print(), 350); };</script>' if auto_print else ""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Packing Slip #{sale.order_number} • {brand_name}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --brand-color: {brand_color};
            --border-color: #cbd5e1;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}
        body {{
            background-color: #f1f5f9;
            color: #0f172a;
            padding: 30px 15px;
            font-size: 13px;
            line-height: 1.5;
        }}
        .print-toolbar {{
            max-width: 820px;
            margin: 0 auto 16px auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #ffffff;
            padding: 12px 20px;
            border-radius: 10px;
            border: 1px solid #cbd5e1;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        }}
        .slip-sheet {{
            max-width: 820px;
            margin: 0 auto;
            background: #ffffff;
            padding: 44px;
            border-radius: 12px;
            border: 2px solid #0f172a;
            box-shadow: 0 10px 25px rgba(0,0,0,0.08);
        }}
        .brand-logo {{
            max-height: 48px;
            max-width: 220px;
            object-fit: contain;
            margin-bottom: 8px;
        }}
        .brand-title {{
            font-size: 22px;
            font-weight: 800;
            color: var(--brand-color);
        }}
        .slip-heading {{
            text-align: right;
        }}
        .slip-title {{
            font-size: 26px;
            font-weight: 900;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        .barcode-strip {{
            background: #f8fafc;
            border: 1px dashed #94a3b8;
            border-radius: 8px;
            padding: 12px 20px;
            margin-top: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-top: 24px;
        }}
        .info-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
        }}
        .info-card h4 {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: #64748b;
            margin-bottom: 6px;
            font-weight: 700;
        }}
        table.pick-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 24px;
        }}
        table.pick-table th {{
            background: #0f172a;
            color: #ffffff;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            padding: 10px 12px;
            text-align: left;
        }}
        table.pick-table td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: middle;
        }}
        .check-box {{
            width: 18px;
            height: 18px;
            border: 2px solid #0f172a;
            border-radius: 4px;
            margin: 0 auto;
        }}
        .qr-section {{
            display: flex;
            align-items: center;
            gap: 20px;
            margin-top: 30px;
            padding: 16px 20px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
        }}
        .qr-render svg {{
            width: 84px;
            height: 84px;
            background: #ffffff;
            padding: 4px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
        }}
        .signoff-box {{
            margin-top: 32px;
            padding-top: 16px;
            border-top: 2px dashed #cbd5e1;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            font-size: 11px;
            color: #475569;
        }}
        .line-blank {{
            border-bottom: 1px solid #0f172a;
            height: 24px;
            margin-top: 4px;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 12px;
            cursor: pointer;
            text-decoration: none;
            border: none;
        }}
        .btn-primary {{
            background: #0f172a;
            color: #ffffff;
        }}
        .btn-secondary {{
            background: #f1f5f9;
            color: #334155;
            border: 1px solid #cbd5e1;
        }}
        .text-center {{ text-align: center; }}
        .text-right {{ text-align: right; }}
        .font-mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
        .font-bold {{ font-weight: 700; }}
        .text-dark {{ color: #0f172a; }}
        .sub-text {{ font-size: 11px; color: #64748b; margin-top: 2px; }}

        @media print {{
            body {{
                background: #ffffff !important;
                padding: 0 !important;
            }}
            .print-toolbar {{
                display: none !important;
            }}
            .slip-sheet {{
                border: none !important;
                box-shadow: none !important;
                padding: 10px 0 !important;
                max-width: 100% !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="print-toolbar">
        <div>
            <span style="font-weight: 800; font-size: 14px;"><i class="fa-solid fa-boxes-packing text-amber-600"></i> Warehouse Packing Slip Preview</span>
            <span style="color: #64748b; font-size: 12px; margin-left: 8px;">#{sale.order_number}</span>
        </div>
        <div style="display: flex; gap: 10px;">
            <button onclick="window.print()" class="btn btn-primary"><i class="fa-solid fa-print"></i> Print Packing Slip</button>
            <button onclick="window.close()" class="btn btn-secondary"><i class="fa-solid fa-xmark"></i> Close</button>
        </div>
    </div>

    <div class="slip-sheet">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                {logo_header}
                <div style="color: #64748b; font-size: 12px;">Warehouse Logistics & Fulfillment Station #04</div>
            </div>
            <div class="slip-heading">
                <div class="slip-title">PACKING SLIP</div>
                <div style="color: #64748b; font-size: 12px;">Order: <strong style="font-family: monospace; color: #0f172a;">#{sale.order_number}</strong></div>
                <div style="color: #64748b; font-size: 12px;">Packed Date: {pack_date_str}</div>
            </div>
        </div>

        <div class="barcode-strip">
            <div>
                <span style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Carrier Service</span>
                <div style="font-weight: 800; font-size: 14px;">{carrier_name}</div>
            </div>
            <div>
                <span style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Master Tracking Number</span>
                <div style="font-family: monospace; font-weight: 700; font-size: 14px;">{tracking_no}</div>
            </div>
            <div>
                <span style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Total Items</span>
                <div style="font-weight: 800; font-size: 14px; text-align: right;">{total_units} Units</div>
            </div>
        </div>

        <div class="grid-2">
            <div class="info-card">
                <h4>Ship To / Destination</h4>
                <div style="font-weight: 700; font-size: 14px; margin-bottom: 2px;">{client_name}</div>
                <p style="color: #475569;">Attn: {contact_name}</p>
                <p style="color: #475569;">Contact: {sale.customer_email or support_email}</p>
                <p style="font-size: 11px; color: #94a3b8; margin-top: 4px;">Standard Receiving Dock - Palletized Freight</p>
            </div>
            <div class="info-card">
                <h4>Origin / Dispatch Facility</h4>
                <div style="font-weight: 700; font-size: 14px; margin-bottom: 2px;">{brand_name} Fulfillment Hub</div>
                <p style="color: #475569;">Autonomous Logistics Center</p>
                <p style="color: #475569;">Support: {support_email}</p>
                <p style="font-size: 11px; color: #94a3b8; margin-top: 4px;">Order Fulfillment Mode: Direct Dispatch</p>
            </div>
        </div>

        <table class="pick-table">
            <thead>
                <tr>
                    <th style="width: 40px;" class="text-center">Pick</th>
                    <th style="width: 45px;" class="text-center">Line</th>
                    <th>Item Description & Warehouse Location</th>
                    <th style="width: 80px;" class="text-center">Qty</th>
                    <th style="width: 80px;" class="text-center">Packed</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>

        <div class="qr-section">
            <div class="qr-render">
                {qr_svg}
            </div>
            <div>
                <div style="font-weight: 700; font-size: 13px; color: #0f172a;"><i class="fa-solid fa-satellite-dish text-indigo-600"></i> Warehouse Telemetry & Dock Scan</div>
                <p style="color: #64748b; font-size: 11px; margin-top: 2px;">Receiving teams can scan this QR code with any camera or scanner to verify live milestone checkpoints, report dock delivery, or inspect shipment manifest details in real time.</p>
                <p style="font-family: monospace; font-size: 10px; color: #94a3b8; margin-top: 4px;">Tracking URL: {tracking_url}</p>
            </div>
        </div>

        <div class="signoff-box">
            <div>
                <span>Picker / Packer Name</span>
                <div class="line-blank"></div>
            </div>
            <div>
                <span>Date & Time Completed</span>
                <div class="line-blank"></div>
            </div>
            <div>
                <span>Dock Inspector Signature</span>
                <div class="line-blank"></div>
            </div>
        </div>
    </div>
    {auto_print_js}
</body>
</html>"""
