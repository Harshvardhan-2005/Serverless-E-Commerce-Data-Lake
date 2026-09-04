"""
Synthetic E-Commerce Data Generator
Author: Gauransh (23/IT/057)

Simulates multi-format chaotic e-commerce data streams with intentionally engineered dirty data anomalies:
  - customers.csv: Missing city values (~10%)
  - products.xml: Raw price formatting containing '$' symbols (~20%)
  - web_events.json: Funnel clickstream with orphaned 'GUEST' user events (~5%)
  - receipts.pdf: Unstructured PDF invoices with billing vs shipping address mismatches (~15%)
"""

import csv
import json
import os
import random
import sys
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from faker import Faker
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Initialize Faker with Indian locale for realistic addresses
fake = Faker('en_IN')

# Configuration Defaults
NUM_CUSTOMERS = 200
NUM_SESSIONS = 250
PROMO_CODES = ["WINTER20", "FREESHIP", "SAVE10", "NONE", "NONE"]
PAYMENT_METHODS = ["UPI", "Visa", "Mastercard", "Cash on Delivery"]
CATEGORIES = ["Electronics", "Clothing", "Home & Kitchen", "Books"]


def generate_batch(batch_no: int, base_dir: str = "Batch"):
    """
    Generates a single micro-batch of multi-format e-commerce data files.
    
    :param batch_no: Sequential batch number (1, 2, 3, ...)
    :param base_dir: Base output directory path
    """
    print(f"\n[INFO] Starting Data Generation for BATCH {batch_no}...")

    # Set unique ID offsets across batches to avoid primary key collisions
    starting_id = (batch_no - 1) * NUM_CUSTOMERS + 1
    global_event_start = (batch_no - 1) * 1000 + 1
    product_start_id = (batch_no - 1) * 20 + 1

    # Directory Structure
    folders = {
        "customers": os.path.join(base_dir, "customers"),
        "events": os.path.join(base_dir, "events"),
        "products": os.path.join(base_dir, "products"),
        "receipts": os.path.join(base_dir, "receipts")
    }

    for path in folders.values():
        os.makedirs(path, exist_ok=True)

    print(f"  ID Offsets -> Users: USR{starting_id:04d}, Events: EVT{global_event_start:05d}, Products: PROD{product_start_id:03d}")

    # ---------------------------------------------------------
    # 1. GENERATE PRODUCTS (XML)
    # ---------------------------------------------------------
    products = []
    root = ET.Element("Catalog")

    for i in range(product_start_id, product_start_id + 20):
        prod_id = f"PROD{i:03d}"
        category = random.choice(CATEGORIES)
        raw_price = round(random.uniform(10.0, 500.0), 2)
        
        # Engineered Anomaly: ~20% of price strings contain '$'
        price_str = f"${raw_price}" if random.random() < 0.20 else str(raw_price)

        products.append({"id": prod_id, "category": category, "price": raw_price})

        prod_element = ET.SubElement(root, "Product")
        ET.SubElement(prod_element, "ProductID").text = prod_id
        ET.SubElement(prod_element, "Category").text = category
        ET.SubElement(prod_element, "Price").text = price_str

    xml_filename = f"products_B{batch_no}.xml"
    xml_path = os.path.join(folders["products"], xml_filename)
    tree = ET.ElementTree(root)
    tree.write(xml_path)
    print(f"  [XML] Generated {xml_filename}")

    # ---------------------------------------------------------
    # 2. GENERATE CUSTOMERS (CSV)
    # ---------------------------------------------------------
    customers = []
    csv_filename = f"customers_B{batch_no}.csv"
    csv_path = os.path.join(folders["customers"], csv_filename)

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'full_name', 'age', 'city', 'state', 'shipping_address'])

        for i in range(starting_id, starting_id + NUM_CUSTOMERS):
            user_id = f"USR{i:04d}"
            name = fake.name()
            age = random.randint(18, 65)
            state = fake.state()

            # Engineered Anomaly: ~10% empty city fields (imputation target)
            city = fake.city() if random.random() > 0.10 else ""
            shipping_addr = fake.address().replace('\n', ', ')

            customers.append({"id": user_id, "addr": shipping_addr})
            writer.writerow([user_id, name, age, city, state, shipping_addr])

    print(f"  [CSV] Generated {csv_filename}")

    # ---------------------------------------------------------
    # 3. GENERATE WEB EVENTS & PDF RECEIPTS (JSON + PDF)
    # ---------------------------------------------------------
    events = []
    global_event_counter = global_event_start

    for _ in range(NUM_SESSIONS):
        # Engineered Anomaly: ~5% orphaned 'GUEST' users
        if random.random() > 0.05:
            user = random.choice(customers)
        else:
            user = {"id": "GUEST", "addr": fake.address().replace('\n', ', ')}

        product = random.choice(products)
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        session_time = datetime.now() - timedelta(days=days_ago, hours=hours_ago)

        funnel_stage = random.choice(['view_only', 'abandoned_cart', 'purchased'])

        # --- EVENT 1: VIEW ---
        events.append({
            "event_id": f"EVT{global_event_counter:05d}",
            "user_id": user["id"],
            "event_type": "view",
            "product_id": product["id"],
            "timestamp": session_time.isoformat()
        })
        global_event_counter += 1

        # --- EVENT 2: ADD TO CART ---
        if funnel_stage in ['abandoned_cart', 'purchased']:
            session_time += timedelta(minutes=random.randint(1, 15))
            events.append({
                "event_id": f"EVT{global_event_counter:05d}",
                "user_id": user["id"],
                "event_type": "add_to_cart",
                "product_id": product["id"],
                "timestamp": session_time.isoformat()
            })
            global_event_counter += 1

            # --- EVENT 3: CHECKOUT & PDF INVOICE ---
            if funnel_stage == 'purchased':
                session_time += timedelta(minutes=random.randint(1, 5))
                events.append({
                    "event_id": f"EVT{global_event_counter:05d}",
                    "user_id": user["id"],
                    "event_type": "checkout",
                    "product_id": product["id"],
                    "timestamp": session_time.isoformat()
                })

                order_id = f"ORD{global_event_counter:05d}"
                promo = random.choice(PROMO_CODES)
                payment = random.choice(PAYMENT_METHODS)

                # Engineered Anomaly: ~15% billing != shipping address (fraud flag)
                if random.random() > 0.15:
                    billing_addr = user["addr"]
                else:
                    billing_addr = fake.address().replace('\n', ', ')

                # Generate Unstructured PDF Receipt
                pdf_path = os.path.join(folders["receipts"], f"{order_id}.pdf")
                c = canvas.Canvas(pdf_path, pagesize=letter)
                c.drawString(50, 750, f"INVOICE #: {order_id}")
                c.drawString(50, 730, f"Date: {session_time.strftime('%Y-%m-%d')}")
                c.drawString(50, 700, f"Customer ID: {user['id']}")
                c.drawString(50, 670, f"Billing Address: {billing_addr}")
                c.drawString(50, 630, "-" * 50)
                c.drawString(50, 600, f"Item: {product['id']} ({product['category']})")
                c.drawString(50, 580, "-" * 50)
                c.drawString(50, 550, f"Payment Method: {payment}")
                c.drawString(50, 530, f"Promo Code Applied: {promo}")
                c.save()

                global_event_counter += 1

    # Chronologically sort events
    events.sort(key=lambda x: x['timestamp'])

    # Write JSON Lines event stream
    json_filename = f"web_events_B{batch_no}.json"
    json_path = os.path.join(folders["events"], json_filename)
    with open(json_path, 'w', encoding='utf-8') as f:
        for event in events:
            f.write(json.dumps(event) + '\n')

    print(f"  [JSON] Generated {json_filename}")
    print(f"  [PDF] Generated receipts in {folders['receipts']}")
    print(f"[SUCCESS] Batch {batch_no} generation complete!\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            batch_num = int(sys.argv[1])
        except ValueError:
            print("Invalid batch number argument. Defaulting to Batch 1.")
            batch_num = 1
    else:
        try:
            val = input("Enter Batch Number (default 1): ").strip()
            batch_num = int(val) if val else 1
        except (ValueError, EOFError):
            batch_num = 1

    generate_batch(batch_num)
