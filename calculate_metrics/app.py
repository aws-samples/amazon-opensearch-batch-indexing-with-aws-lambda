import json
import boto3
import codecs
import botocore
import botocore.exceptions
import pandas as pd


def lambda_handler(event, context):
    ## Get event values
    source_bucket = event['source_bucket']
    destination_bucket = event['destination_bucket']
    key = event["key"]

    def download_data(key):
        s3 = boto3.client(service_name='s3', region_name='eu-west-1')
        # s3.download_file(, key, '/tmp/data.json')
        print('\Data downloaded.')
        print("bucket:{},key:{}".format(source_bucket, key))

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

    # Save the new JSON file to an S3 bucket
    def upload_data_with_id(data):
        s3 = boto3.client(service_name='s3', region_name='eu-west-1')
        # Convert Python list to Pandas dataframe
        df = pd.DataFrame(data)
        # Save in JSON
        df.to_json("/tmp/metrics.json", orient="records", force_ascii=False)
        # Upload file to S3 with new 'source' and 'id' fields
        s3.upload_file('/tmp/metrics.json', destination_bucket, "metrics.json")

    ## Execution Flow

    # 1 - get the connection string for the Opensearch cluster
    comprehend = boto3.client(service_name='comprehend', region_name='eu-west-1')
    # 2 - Download the data from S3
    download_data(key)
    # 3 - Load data to a Python dictionary
    data = load_data()
    # 4 - Calculate Metrics
    metrics = []
    for comment in data:
        sentiment = comprehend.detect_sentiment(Text=comment['review_body'], LanguageCode='es')
        comment["Sentiment"] = sentiment['Sentiment']
        metrics.append({key: comment[key] for key in comment.keys() & {'id', 'Sentiment'}})
    # 5 - Upload metrics to S3
    upload_data_with_id(metrics)

    return {
        'statusCode': 200,
        'body': json.dumps('Metrics have been calculated and uploaded!')
    }
