import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv('e:/Working Capital/Working-Capital-AI/.env')
DATABASE_URL = os.getenv('DATABASE_URL')

def check_names():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT company_name FROM \"Customer\"')
            customers = [r['company_name'] for r in cur.fetchall()]
            
            cur.execute('SELECT company_name FROM \"Vendor\"')
            vendors = [r['company_name'] for r in cur.fetchall()]
            
            print(f"Customers: {customers}")
            print(f"Vendors: {vendors}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_names()
