import requests
import json
from app.core.config import settings
from app.services.rag_service import rag_service
from app.services.db_service import db_service
from typing import Dict, Any, List

class AILogicService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = settings.MODEL_NAME

    def _call_llama(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1, # Low temperature for SQL generation/logic
            "max_tokens": 1000
        }
        response = requests.post(self.api_url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"Groq API Error Status: {response.status_code}")
            print(f"Groq API Error Response: {response.text}")
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _rewrite_query(self, user_message: str, history: List[Dict[str, str]]) -> str:
        """
        Rewrite a follow-up query into a standalone query using conversation history.
        Example: "what is the count" -> "What is the count of steel plates we purchased?"
        """
        if not history:
            return user_message
            
        # Get last 3 turns for context
        recent_history = history[-3:]
        history_text = ""
        for m in recent_history:
            role = m.get('role', 'User').capitalize()
            content = m.get('content', '')
            history_text += f"{role}: {content}\n"
        
        system_rewrite_prompt = """
        You are a query-rewriting assistant. 
        Given a conversation history and a final follow-up question, rewrite it into a single, standalone question that contains all the necessary context from the history. 
        If it's already a standalone question, don't change it.
        
        Example 1:
        History: "How many steel plates did we buy?" AI: "We bought 50."
        Follow-up: "what was the cost?"
        Rewritten: "What was the cost of the steel plates we bought?"
        
        Return ONLY the rewritten question.
        """
        
        user_prompt = f"History:\n{history_text}\n\nFinal Question: {user_message}"
        
        try:
            rewritten = self._call_llama(system_rewrite_prompt, user_prompt).strip()
            return rewritten
        except:
            return user_message

    async def process_chat(self, user_message: str, history: List[Dict[str, str]] = []) -> str:
        # Step 0: Rewrite the query if there's history
        rewritten_message = self._rewrite_query(user_message, history or [])
        print(f"DEBUG: Standalone query: {rewritten_message}")

        # Step 1: Retrieve relevant schema context via RAG
        schema_context = rag_service.retrieve_relevant_context(rewritten_message, n_results=10)
        schema_text = "\n".join([c["document"] for c in schema_context])

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
        - START the response directly with SELECT.
        
        Context Schema:
        {schema_text}
        
        Business Rules for Financial Accuracy:
        1. GRANULARITY: 
           - 'Purchase/Sale/Invoice' (without 'item/product') = Use Header tables (`PurchaseInvoice` or `SalesInvoice`) and `total_amount`.
           - 'Product/Item/Price' = Use Item tables (`PurchaseInvoiceItem` or `SalesInvoiceItem`) and `unit_price` or `total`.
        2. PROFIT/LOSS (Net Income):
           - Formula: (SUM of SalesInvoice.total_amount) - (SUM of PurchaseInvoice.total_amount).
           - ALWAYS exclude Invoices with status='Cancelled'.
        3. WORKING CAPITAL (Net):
           - Formula: (Receivables) - (Payables). 
           - Receivables: SUM of (SalesInvoice.total_amount - SalesInvoice.paid_amount) where status != 'Cancelled'.
           - Payables: SUM of (PurchaseInvoice.total_amount - PurchaseInvoice.paid_amount) where status != 'Cancelled'.
        4. ENTITY DIFFERENTIATION (CRITICAL):
           - Customers and Vendors are DIFFERENT. 
           - Customer info is in the `Customer` table. 
           - Vendor info is in the `Vendor` table.
           - If asked for names or counts of both, query BOTH tables (e.g. using UNION or separate subqueries). NEVER say they are indistinguishable.
        5. CROSS-TABLE AGGREGATION (CRITICAL):
           - NEVER use 'JOIN' between unrelated transaction tables (e.g. Sales vs Purchase).
           - NEVER use 'JOIN ... ON TRUE'.
           - ALWAYS use independent subqueries to avoid Cartesian products (duplication).
        6. DATA TYPES & FUZZY SEARCH:
           - 'id' fields are UUID (TEXT). No 'id > 0' comparisons.
           - Use 'ILIKE %word%' for fuzzy item/customer searches.
        """
        
        try:
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
            system_synth_prompt = """
            You are a helpful business assistant. Given a user's question and the raw data from the database, provide a clear, professional, and concise answer.
            If the data is empty or null, say that no records were found.
            Format numbers as currency (₹) where appropriate.
            """
            
            synth_user_prompt = f"""
            User Question: {user_message}
            Raw Data from DB: {json.dumps(data_results, default=str)}
            
            Provide the final answer.
            """
            
            final_answer = self._call_llama(system_synth_prompt, synth_user_prompt)
            return final_answer

        except Exception as e:
            print(f"Chat Pipeline Error: {e}")
            return f"I encountered an error while processing your request: {str(e)}"

ai_logic_service = AILogicService()
