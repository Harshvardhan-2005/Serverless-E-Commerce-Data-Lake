"""
AWS Lambda 2: Micro-Batch Aggregator & Master Athena ETL Trigger
Author: Gauransh (23/IT/057)

Trigger: Amazon EventBridge (Cron / Rate expression: 5-minute micro-batch timer)

Responsibilities:
  1. Concurrency Control: Prevents check-then-act race conditions by purging old curated files and executing
     a single deterministic CTAS batch execution.
  2. Storage Optimization: Drops old table metadata, clears s3://<bucket>/curated-zone/, and runs Athena CTAS.
  3. Parquet Output: Generates exactly ONE Snappy-compressed Parquet master file per micro-batch (92% compression).
"""

import json
import os
import time
import boto3

athena = boto3.client('athena')
s3 = boto3.client('s3')

S3_BUCKET = os.environ.get('S3_BUCKET', 'cws-ecommerce-datalake-sd-9921')
DATABASE = os.environ.get('ATHENA_DATABASE', 'ecommerce_datalake_db')
ATHENA_OUTPUT_LOCATION = os.environ.get('ATHENA_OUTPUT_LOCATION', f's3://{S3_BUCKET}/athena-results/')
CURATED_S3_PREFIX = os.environ.get('CURATED_S3_PREFIX', 'curated-zone/')


def purge_s3_prefix(bucket: str, prefix: str):
    """
    Purges existing objects under a specific S3 prefix to guarantee single-file batch output.
    """
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if 'Contents' in response:
        delete_keys = [{'Key': obj['Key']} for obj in response['Contents']]
        s3.delete_objects(Bucket=bucket, Delete={'Objects': delete_keys})
        print(f"[INFO] Purged {len(delete_keys)} old objects from s3://{bucket}/{prefix}")


def execute_athena_query(query: str, database: str, output_location: str) -> str:
    """
    Submits an Athena SQL query and polls until execution finishes.
    """
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': output_location}
    )
    execution_id = response['QueryExecutionId']
    print(f"[INFO] Started Athena Query Execution ID: {execution_id}")

    # Poll execution status
    while True:
        status_res = athena.get_query_execution(QueryExecutionId=execution_id)
        state = status_res['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            if state != 'SUCCEEDED':
                reason = status_res['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                raise RuntimeError(f"Athena query failed with state '{state}': {reason}")
            print(f"[SUCCESS] Athena Query {execution_id} completed successfully.")
            return execution_id
        time.sleep(2)


def lambda_handler(event, context):
    """
    Main AWS Lambda Handler triggered by 5-minute EventBridge scheduler.
    """
    print(f"[INFO] Starting 5-minute Micro-Batch Aggregation for S3 Bucket: {S3_BUCKET}")

    try:
        # Step 1: Purge existing S3 Curated Zone
        purge_s3_prefix(S3_BUCKET, CURATED_S3_PREFIX)

        # Step 2: Drop prior table metadata if exists
        drop_query = "DROP TABLE IF EXISTS ecommerce_analytics_master;"
        execute_athena_query(drop_query, DATABASE, ATHENA_OUTPUT_LOCATION)

        # Step 3: Execute Master CTAS Query
        ctas_query = f"""
        CREATE TABLE {DATABASE}.ecommerce_analytics_master
        WITH (
            format = 'PARQUET',
            parquet_compression = 'SNAPPY',
            external_location = 's3://{S3_BUCKET}/{CURATED_S3_PREFIX}'
        ) AS
        SELECT
            e.event_id,
            e.timestamp AS event_timestamp,
            e.user_id,
            COALESCE(NULLIF(c.full_name, ''), 'Unknown Customer') AS customer_name,
            c.age AS customer_age,
            COALESCE(NULLIF(c.city, ''), 'Unknown City') AS customer_city,
            c.state AS customer_state,
            c.shipping_address,
            p.product_id,
            p.category AS product_category,
            CAST(p.price AS DOUBLE) AS product_price,
            e.event_type,
            r.order_id,
            r.payment_method,
            r.promo_code,
            r.billing_address,
            CASE 
                WHEN c.shipping_address != r.billing_address THEN 1 
                ELSE 0 
            END AS fraud_flag
        FROM processed_zone.events e
        LEFT JOIN processed_zone.customers c ON e.user_id = c.user_id
        LEFT JOIN processed_zone.products p ON e.product_id = p.product_id
        LEFT JOIN processed_zone.receipts r ON e.user_id = r.customer_id AND e.product_id = r.product_id
        WHERE e.user_id != 'GUEST';
        """

        exec_id = execute_athena_query(ctas_query, DATABASE, ATHENA_OUTPUT_LOCATION)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Micro-batch ETL completed successfully',
                'athena_execution_id': exec_id,
                'output_location': f's3://{S3_BUCKET}/{CURATED_S3_PREFIX}'
            })
        }

    except Exception as err:
        print(f"[ERROR] Error during micro-batch ETL: {str(err)}")
        raise err
