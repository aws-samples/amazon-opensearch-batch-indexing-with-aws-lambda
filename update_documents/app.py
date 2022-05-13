import json
import boto3
from opensearchpy import OpenSearch, helpers
import codecs


def lambda_handler(event, context):
    ## Get event values
    source_bucket = event['source_bucket']
    key = event["key"]
    index = event['index']
    domain_endpoint = event['domain_endpoint']

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
        s3.download_file(source_bucket, key, '/tmp/data.json')
        print('\Data downloaded.')

    # Loads the data to a Python dictionary
    def load_data():
        data = json.load(codecs.open('/tmp/data.json', 'r', 'utf-8-sig'))
        return data

    # Takes the id column of the document to update, which is the id of the Opensearch document
    # and updates the document with the new fields
    def update_documents(connection_string, data):
        client = OpenSearch([connection_string])

        def gendata():
            for document in data:
                index_id = int(document['id'])
                # Delete 'id' column because we don't want to index it
                yield {
                    "_op_type": "update",
                    "_id": index_id,
                    "_index": index,
                    "doc": document,
                }

        response = helpers.bulk(client, gendata(), request_timeout=60)
        print('\nUpdating document')
        print(response)

    ## Execution Flow

    # 1 - get the connection string for the Opensearch cluster
    connection_string = get_connection_string()
    # 2 - Download the data from S3
    download_data(key)
    # 3 - Load data to a Python dictionary
    data = load_data()
    # 4 - Update documents in the Opensearch index
    update_documents(connection_string, data)

    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('Updating completed!'),
    }
