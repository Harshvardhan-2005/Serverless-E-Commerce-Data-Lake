"""
AWS Lambda 1: Parsing & Extraction Engine
Author: Gauransh (23/IT/057)

Trigger: S3 PutObject Event on Raw Zone (s3://<bucket_name>/raw-zone/)

Responsibilities:
  1. XML Catalog Flattening: Flattens products.xml into tabular CSV, cleaning dirty '$' characters in prices.
  2. PDF OCR / Text Extraction: Parses unstructured PDF receipt invoices using PyPDF2, extracting key attributes
     (Invoice ID, Promo Code, Payment Method, Billing Address) and outputting CSV files to the Processed Zone.
"""

import csv
import io
import json
import os
import urllib.parse
import xml.etree.ElementTree as ET
import boto3
from PyPDF2 import PdfReader

s3 = boto3.client('s3')

PROCESSED_PREFIX = os.environ.get('PROCESSED_PREFIX', 'processed-zone')


def lambda_handler(event, context):
    """
    Main AWS Lambda Handler triggered by S3 PutObject events.
    """
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'], encoding='utf-8')
        print(f"[INFO] Processing object: s3://{bucket}/{key}")

        # ---------------------------------------------------------
        # 1. PARSE & FLATTEN XML (Catalog / Products)
        # ---------------------------------------------------------
        if key.endswith('.xml'):
            response = s3.get_object(Bucket=bucket, Key=key)
            xml_content = response['Body'].read()
            root = ET.fromstring(xml_content)

            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(['product_id', 'category', 'price'])

            for product in root.findall('Product'):
                p_id = product.find('ProductID').text if product.find('ProductID') is not None else ""
                cat = product.find('Category').text if product.find('Category') is not None else ""
                raw_price = product.find('Price').text if product.find('Price') is not None else "0.0"

                # CLEAN ANOMALY: Strip '$' character if present
                clean_price = raw_price.replace('$', '').strip()
                writer.writerow([p_id, cat, clean_price])

            output_key = f"{PROCESSED_PREFIX}/products.csv"
            s3.put_object(
                Bucket=bucket,
                Key=output_key,
                Body=csv_buffer.getvalue(),
                ContentType='text/csv'
            )
            print(f"[SUCCESS] Flattened XML and uploaded to s3://{bucket}/{output_key}")

        # ---------------------------------------------------------
        # 2. PARSE & EXTRACT UNSTRUCTURED PDF (Receipts / Invoices)
        # ---------------------------------------------------------
        elif key.endswith('.pdf'):
            response = s3.get_object(Bucket=bucket, Key=key)
            pdf_bytes = io.BytesIO(response['Body'].read())
            reader = PdfReader(pdf_bytes)

            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"

            order_id = "UNKNOWN"
            customer_id = "UNKNOWN"
            promo = "NONE"
            payment = "UNKNOWN"
            billing = "UNKNOWN"

            for line in text.split('\n'):
                line_str = line.strip()
                if "INVOICE #:" in line_str:
                    order_id = line_str.split("INVOICE #:")[1].strip()
                elif "Customer ID:" in line_str:
                    customer_id = line_str.split("Customer ID:")[1].strip()
                elif "Promo Code" in line_str:
                    promo = line_str.split("Promo Code Applied:")[1].strip()
                elif "Payment Method:" in line_str:
                    payment = line_str.split("Payment Method:")[1].strip()
                elif "Billing Address:" in line_str:
                    billing = line_str.split("Billing Address:")[1].strip()

            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(['order_id', 'customer_id', 'promo_code', 'payment_method', 'billing_address'])
            writer.writerow([order_id, customer_id, promo, payment, billing])

            output_key = f"{PROCESSED_PREFIX}/receipts/{order_id}.csv"
            s3.put_object(
                Bucket=bucket,
                Key=output_key,
                Body=csv_buffer.getvalue(),
                ContentType='text/csv'
            )
            print(f"[SUCCESS] Extracted PDF invoice {order_id} and uploaded to s3://{bucket}/{output_key}")

    return {
        'statusCode': 200,
        'body': json.dumps('Processing Complete')
    }
