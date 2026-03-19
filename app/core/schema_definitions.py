from typing import List, Dict, Any

# Metadata for RAG indexing. 
# This helps the LLM understand which tables and fields to use for different questions.
SCHEMA_METADATA: List[Dict[str, Any]] = [
    {
        "table": "Customer",
        "description": "Information about customers (clients). Use for 'who is our top customer', 'who owes most', or 'contact info'.",
        "fields": [
            {"name": "id", "description": "System UUID. NOT used for SalesInvoice join."},
            {"name": "customer_id", "description": "Human-readable ID (e.g. CUST-1001). JOIN with SalesInvoice.customer_id_ref."},
            {"name": "company_name", "description": "Legal name of the CUSTOMER company. Use when the user asks for customer names."},
            {"name": "outstanding_balance", "description": "Total amount OWED TO US by this customer. Used for receivables."},
            {"name": "avg_payment_days", "description": "Average delay in customer payments."}
        ]
    },
    {
        "table": "Vendor",
        "description": "Information about vendors (suppliers). Use for 'who are our suppliers' or 'spending' questions.",
        "fields": [
            {"name": "id", "description": "Primary key. JOIN with PurchaseInvoice.vendor_id."},
            {"name": "vendor_id", "description": "Human-readable ID (NOT used for joins)."},
            {"name": "company_name", "description": "Legal name of the VENDOR company. Use when the user asks for vendor/supplier names."},
            {"name": "outstanding_payable", "description": "Total amount WE OWE to this vendor. Used for payables."}
        ]
    },
    {
        "table": "SalesInvoice",
        "description": "Records of sales invoices. Use for 'sales', 'revenue', 'total sales', 'most expensive sale', and 'invoice' questions. Join with Customer on Customer.customer_id = SalesInvoice.customer_id_ref.",
        "fields": [
            {"name": "id", "description": "Primary key. Join with SalesInvoiceItem.invoice_id."},
            {"name": "invoice_no", "description": "Sales invoice number."},
            {"name": "invoice_date", "description": "Date of sale."},
            {"name": "total_amount", "description": "Total value of the invoice. ALWAYS use this for 'most expensive' or 'total' sales questions."},
            {"name": "paid_amount", "description": "Amount already paid."},
            {"name": "status", "description": "State: 'Pending', 'Paid', 'PartiallyPaid', 'Overdue', 'Cancelled'."},
            {"name": "customer_id_ref", "description": "Foreign key to Customer.customer_id (the human ID)."}
        ]
    },
    {
        "table": "PurchaseInvoice",
        "description": "Records of purchase invoices. Use for 'spent', 'spending', 'expenses', 'most expensive purchase', and 'invoice' questions. Join with Vendor on Vendor.id = PurchaseInvoice.vendor_id.",
        "fields": [
            {"name": "id", "description": "Primary key. Join with PurchaseInvoiceItem.invoice_id."},
            {"name": "invoice_no", "description": "Purchase invoice number."},
            {"name": "invoice_date", "description": "Date of purchase."},
            {"name": "total_amount", "description": "Total value of the entire purchase. ALWAYS use this for 'most expensive purchase' or 'spending' questions."},
            {"name": "paid_amount", "description": "Amount we paid."},
            {"name": "vendor_id", "description": "Foreign key to Vendor.id (the UUID)."}
        ]
    },
    {
        "table": "SalesInvoiceItem",
        "description": "Individual line items in a Sales Invoice. Use ONLY for questions about specific 'items', 'products', or 'quantities'. Join with SalesInvoice on SalesInvoice.id = SalesInvoiceItem.invoice_id.",
        "fields": [
            {"name": "invoice_id", "description": "Foreign key to SalesInvoice.id."},
            {"name": "item_name", "description": "Name of product/service sold. Use for 'what items' or searching for specific products."},
            {"name": "quantity", "description": "Number of units sold."},
            {"name": "unit_price", "description": "Price per unit."},
            {"name": "total", "description": "Total line value (qty * price)."}
        ]
    },
    {
        "table": "PurchaseInvoiceItem",
        "description": "Individual line items in a Purchase Invoice. Use ONLY for questions about specific 'items', 'products bought', or 'quantities'. Join with PurchaseInvoice on PurchaseInvoice.id = PurchaseInvoiceItem.invoice_id.",
        "fields": [
            {"name": "invoice_id", "description": "Foreign key to PurchaseInvoice.id."},
            {"name": "item_name", "description": "Name of product/service bought. Use for 'what items' or searching for specific products."},
            {"name": "quantity", "description": "Number of units bought."},
            {"name": "unit_price", "description": "Price per unit."},
            {"name": "total", "description": "Total line value (qty * price)."}
        ]
    }
]
