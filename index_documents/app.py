import json
import boto3
from opensearchpy import OpenSearch, helpers
import pandas as pd
import os
import botocore
import botocore.exceptions
import codecs


def lambda_handler(event, context):
    ## Get event values
    source_bucket = event['source_bucket']
    destination_bucket = event['destination_bucket']
    domain_endpoint = event['domain_endpoint']
    key = event["key"]
    index = event['index']

    ## Helper Functions

    # Get secret stored in secrets manager
    def get_secret(secret_name):
        region_name = "us-east-1"
        # Create a Secrets Manager client
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )

        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        return get_secret_value_response

    # Reconstruct the connection string to the Opensearch cluster
    def get_connection_string():
        user = get_secret(secret_name="os-username")['SecretString']
        password = get_secret(secret_name="os-password")['SecretString']

        connection_string = "https://{}:{}@{}:443".format(user, password, domain_endpoint)

        return connection_string

    # Downloads the data from S3
    def download_data(key):
        s3 = boto3.client(service_name='s3', region_name='eu-west-1')
        try:
            response = s3.download_file(source_bucket, key, '/tmp/data.json')
            print("response: {}".format(response))
        except botocore.exceptions.ClientError as e:
            print(e.response['Error']['Code'])
            print("The object does not exist.")

    # Loads the data to a Python dictionary
    def load_data():
        data = json.load(codecs.open('/tmp/data.json', 'r', 'utf-8-sig'))
        return data

    def add_source_and_id_column(data):
        id = 0
        for document in data:
            id += 1
            document['id'] = id
        print("Add id and source columns")

    def insert_documents(data):
        client = OpenSearch([connection_string])

        def gendata():
            for document in data:
                id = document['id']
                yield {
                    "_id": id,
                    "_index": index,
                    "_source": document,
                }

        response = helpers.bulk(client, gendata())
        print("\nIndexing Documents")
        print(response)

    # Save the new JSON file to an S3 bucket
    def upload_data_with_id(data):
        s3 = boto3.client(service_name='s3', region_name='eu-west-1')
        # Convert Python list to Pandas dataframe
        df = pd.DataFrame(data)
        # Change type of id to int
        df['id'] = df['id'].astype(int)
        # Save in JSON oneline
        df.to_json("/tmp/metrics.json", orient="records", force_ascii=False)
        # Upload file to S3 with new 'source' and 'id' fields
        s3.upload_file('/tmp/metrics.json', destination_bucket, key)

    ## Execution Flow

    # 1 - Download the data from S3
    download_data(key)
    # 2 - Get the connection string for the Opensearch cluster
    connection_string = get_connection_string()
    # 3 - Load data to a Python dictionary
    data = load_data()
    # 4 - Add source column to the dictionary
    add_source_and_id_column(data)
    # 5 - Insert documents in the Opensearch index
    insert_documents(data)
    # 6 - Upload data with the id and source field back to the S3 bucket
    upload_data_with_id(data)
    # Delete file from /tmp folder
    os.remove('/tmp/data.json')
    os.remove('/tmp/metrics.json')

    return {
        'statusCode': 200,
        'body': json.dumps('Indexing completed!'),
    }
