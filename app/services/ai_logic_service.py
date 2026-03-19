import requests
import json
from app.core.config import settings
from app.core.schema_definitions import SCHEMA_METADATA
from app.services.db_service import db_service
from typing import Dict, Any, List

class AILogicService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = settings.MODEL_NAME

    def _call_llama(self, system_prompt: str, user_prompt: str) -> str:
        import time
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "temperature": 0.1, "max_tokens": 1000
        }
        for attempt in range(3):
            response = requests.post(self.api_url, headers=headers, json=payload)
            if response.status_code == 429:
                time.sleep(2)
                continue
            if response.status_code != 200:
                print(f"Groq API Error Status: {response.status_code}. Response: {response.text}")
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        raise Exception("Groq Rate Limit exceeded after retries")

    # removed _rewrite_query as per user request for direct querying

    async def process_chat(self, user_message: str, history: List[Dict[str, str]] = []) -> str:
        # Step 1: Use ENTIRE schema metadata (ensures 100% join accuracy for small schema)
        schema_text = f"--- FULL DATABASE SCHEMA ---\n{json.dumps(SCHEMA_METADATA, indent=2)}"

        # Step 2: Generate SQL Query using Llama 3.3 70B
        system_sql_prompt = f"""
        You are a SQL expert for a PostgreSQL database. 
        Given a user question and schema metadata, generate a valid SELECT query.
        
        Join Logic (CRITICAL):
        - Join "SalesInvoice" with "Customer" on "SalesInvoice"."customer_id_ref" = "Customer"."customer_id"
        - Join "PurchaseInvoice" with "Vendor" on "PurchaseInvoice"."vendor_id" = "Vendor"."id"
        - Join "SalesInvoiceItem" with "SalesInvoice" on "SalesInvoiceItem"."invoice_id" = "SalesInvoice"."id"
        - Join "PurchaseInvoiceItem" with "PurchaseInvoice" on "PurchaseInvoiceItem"."invoice_id" = "PurchaseInvoice"."id"
        
        PostgreSQL Rules:
        1. Always use double quotes for all table and column names (e.g., "SalesInvoice"."total_amount").
        2. FUZZY SEARCH: For company names or product items, use 'ILIKE' with wildcards between words to handle plurals or partial matches (e.g., "item_name" ILIKE '%steel%plate%' to match "Steel Plate", "Steel Plates", or "Stainless Steel Plate").
        3. CRITICAL: When using GROUP BY, you CANNOT use "SELECT *". You MUST list specific columns in SELECT, and EVERY one of those non-aggregated columns MUST be in the GROUP BY clause.
        4. TOP N SUM: To get the SUM of the 'Top 5' or 'Last 5' records, use a subquery (e.g., SELECT SUM("total_amount") FROM (SELECT "total_amount" FROM "SalesInvoice" ORDER BY "invoice_date" DESC LIMIT 5) as sub).
        
        Example for 'Top Customer':
        SELECT "Customer"."company_name", SUM("SalesInvoice"."total_amount") as total_sales
        FROM "Customer"
        JOIN "SalesInvoice" ON "SalesInvoice"."customer_id_ref" = "Customer"."customer_id"
        GROUP BY "Customer"."company_name"
        ORDER BY total_sales DESC
        LIMIT 1;
        
        - "Top customer" or "Best client" means the one with the highest SUM("SalesInvoice"."total_amount").
        - "Who owes most" means the one with the highest "Customer"."outstanding_balance".
        
        CRITICAL: Return ONLY the raw SQL query. 
        - DO NOT include any preamble like "To find the...", "Here is the query...", etc.
        - DO NOT include markdown backticks.
        - DO NOT include any explanation.
        CRITICAL: The 'Context Schema' below describes TABLES and FIELDS, NOT the actual data rows. 
        - DO NOT look for specific company names (like 'Apex' or 'Steel') in the schema text.
        - ASSUME company names exist in the 'company_name' field of the 'Customer' or 'Vendor' tables.
        - ASSUME item names exist in the 'item_name' field of the 'Item' tables.
        
        Context Schema:
        {schema_text}
        
        Business Rules for Financial Accuracy:
        1. GRANULARITY: 
           - 'Purchase/Sale/Invoice' (without 'item/product') = Use Header tables (`PurchaseInvoice` or `SalesInvoice`) and `total_amount`.
           - 'Product/Item/Price' = Use Item tables (`PurchaseInvoiceItem` or `SalesInvoiceItem`) and `unit_price` or `total`.
        2. BALANCES & WORKING CAPITAL (CRITICAL):
           - NEVER use 'outstanding_balance' or 'outstanding_payable' fields from Customer/Vendor tables (they may be stale).
           - ALWAYS calculate balances by summing (total_amount - paid_amount) from Invoice tables.
           - ALWAYS exclude status='Cancelled'.
        3. NAME-BASED SEARCH & JOINS (CRITICAL):
           - Invoices and Entities (Customer/Vendor) are Linked.
           - When searching for a Company Name (e.g. 'Apex'), ALWAYS JOIN the transaction table to the Entity table.
           - NEVER say a company is 'not found' without checking the Entity table first using ILIKE.
        4. QUANTITY vs VALUE:
           - "How many" or "Count of items" = Use SUM(quantity).
           - "How much", "Worth", or "Total cost" = Use SUM(total).
        5. CROSS-TABLE AGGREGATION (MANDATORY):
           - NEVER 'JOIN' unrelated tables (e.g. SalesInvoice vs PurchaseInvoice).
           - ALWAYS use the SUBQUERY pattern for 'Working Capital' or 'Profit/Loss'.
           - CORRECT WORKING CAPITAL TEMPLATE: 
             SELECT ( (SELECT SUM("total_amount" - "paid_amount") FROM "SalesInvoice" WHERE "status" != 'Cancelled') - (SELECT SUM("total_amount" - "paid_amount") FROM "PurchaseInvoice" WHERE "status" != 'Cancelled') ) as working_capital;
        6. DATA TYPES & FUZZY SEARCH (ROBUST):
           - 'id' fields are UUID (TEXT). No 'id > 0' comparisons.
           - Use 'ILIKE %word%' for fuzzy item/customer searches.
           - PLURAL RESILIENCE: If a user uses a plural word (e.g. "Steel Plates", "Aluminium Sheets"), ALWAYS use the singular stem in the SQL search (e.g. "item_name" ILIKE '%Steel%Plate%'). Singular DB records will NOT match plural search terms.
        7. SELECTION EVIDENCE (CRITICAL):
           - If the user filters by a name (e.g. Vendor Name or Item Name), you MUST include that name field in the SELECT clause (e.g. SELECT "Vendor"."company_name", ...). This allows the final response to confirm the match to the user.
        """
        
        try:
            # Treating every query as standalone as per user request
            raw_sql = self._call_llama(system_sql_prompt, user_message).strip()
            
            # Post-processing: Extract only the SELECT statement if LLM included preamble
            sql_query = raw_sql
            if "SELECT" in raw_sql.upper():
                start_idx = raw_sql.upper().find("SELECT")
                # Find end of query (usually till semicolon or end of string)
                end_idx = raw_sql.find(";", start_idx)
                if end_idx != -1:
                    sql_query = raw_sql[start_idx:end_idx+1]
                else:
                    sql_query = raw_sql[start_idx:]
            
            # Remove any markdown backticks if present
            sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            
            print(f"DEBUG: Generated SQL for '{user_message}':\n{sql_query}")
            
            if sql_query.startswith("ERROR"):
                # Handle greetings or non-DB questions naturally
                general_synth_prompt = """
                You are a helpful business assistant for SNS (a Working Capital platform). 
                If the user greets you (e.g., "hii", "hello") or asks general questions, respond politely and professionally.
                Remind them that you can help with questions about customers, vendors, and invoices.
                """
                return self._call_llama(general_synth_prompt, user_message)

            # Step 3: Execute SQL Query
            data_results = db_service.execute_query(sql_query)
            print(f"DEBUG: Data Results for '{user_message}':\n{json.dumps(data_results, default=str)}")

            # Step 4: Synthesize Final Answer
            system_synth_prompt = f"""
            You are a helpful business assistant for SNS (Working Capital platform).
            Given a user's question and the raw data from the database, provide a clear, professional, and concise answer.
            
            Context Schema:
            {schema_text}
            
            Business Rules:
            1. Strictly distinguish "How many/Count" (Quantity) from "How much/Worth" (Currency ₹).
            2. For quantities, do NOT use ₹.
            3. TAX AWARENESS: The `total` field in the database usually includes TAX (e.g. 18% GST). If `quantity * unit_price` does not exactly match `total`, do NOT call it a "discrepancy". Just report the `total` as provided.
            4. EVIDENTIARY TRUTH: If the user filters for a name (e.g. "Apex"), and data is returned, confirm it is from that entity. Do NOT say "it cannot be confirmed" if the SQL search was performed.
            5. If the data results are empty, say clearly that no records were found for that specific search.
            """
            
            synth_user_prompt = f"""
            User Question: {user_message}
            Raw Data from DB: {json.dumps(data_results, default=str)}
            
            Provide the final answer based ONLY on the data provided.
            """
            
            final_answer = self._call_llama(system_synth_prompt, synth_user_prompt)
            return final_answer

        except Exception as e:
            print(f"Chat Pipeline Error: {e}")
            return f"I encountered an error while processing your request: {str(e)}"

ai_logic_service = AILogicService()
