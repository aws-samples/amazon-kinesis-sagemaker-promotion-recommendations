# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from __future__ import print_function
import base64
import json
import boto3
import csv
import array
import os
import traceback
import re

table = os.environ['PartitionFor']
databaseName = os.environ['DatabaseName']
prefix = os.environ['PartitionPrefix']
client = boto3.client('glue')
ddbtable = os.environ['DdbTable']
ddbclient = boto3.client('dynamodb')
ddbstreams = os.environ['DdbStreams']
allowed_streams = ddbstreams.split(',')

def handler(event, context):

    bad_records = []
    bad_inserts = []
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key'] 
        print("Detected create event: {0}/{1}".format(bucket, key))

        m = re.search(prefix + '\/(\d{4})\/(\d{2})\/(\d{2})\/(\d{2})', key)
        if m == None:
            print("Did not find partition pattern, skipping: {0}".format(key))
            continue
        year = m.group(1)
        month = m.group(2)
        day = m.group(3)
        hour = m.group(4)
        partition = "{0}/{1}/{2}/{3}".format(year, month, day, hour)

        # record this new file in our DynamoDB log
        try:
            if table in allowed_streams:
                ddbresponse = ddbclient.put_item(
                    Item={
                        'File': {
                            'S': "{0}/{1}".format(bucket, key),
                        },
                        'IsProcessed': {
                            'N': '0',
                        },
                        'Stream': {
                            'S': table,
                        },
                    },
                    ReturnConsumedCapacity='TOTAL',
                    TableName=ddbtable
                )
        except Exception as e:
            trc = traceback.format_exc()
            print("Error recording new file {0}/{1} in DynamoDB: {2}".format(bucket, key, trc))
            bad_inserts.append(partition)

        # See if partition already exists
        exists = True
        tbl = None
        try:
            tbl = client.get_table(
                DatabaseName=databaseName,
                Name=table
            )
            response = client.get_partition(
                DatabaseName=databaseName,
                TableName=table,
                PartitionValues=[
                    year,
                    month,
                    day,
                    hour
                ]
            )
            print("Partition {0} already exists for table {1}, skipping".format(partition, table))
        except Exception as e:
            exists = False
            print("Partition {0} does not exist for table {1}, creating".format(partition, table))

        if exists == False:
            try:
                sdescriptor = tbl['Table']['StorageDescriptor']
                response = client.create_partition(
                    DatabaseName=databaseName,
                    TableName=table,
                    PartitionInput={
                        'Values': [
                            year,
                            month,
                            day,
                            hour
                        ],
                        'StorageDescriptor': {
                            'Columns': sdescriptor['Columns'],
                            'Location': "{0}/{1}/".format(sdescriptor['Location'], partition),
                            'InputFormat': sdescriptor['InputFormat'],
                            'OutputFormat': sdescriptor['OutputFormat'],
                            'Compressed': True,
                            'SerdeInfo': sdescriptor['SerdeInfo'],
                            'Parameters': sdescriptor['Parameters'],
                            'StoredAsSubDirectories': False
                        },
                        'Parameters': tbl['Table']['Parameters']
                    }
                )

            except Exception as e:
                trc = traceback.format_exc()
                print("Error creating partition {0} for table {1}: {2}".format(partition, table, trc))
                bad_records.append(partition)

        return 'Processed {0} records, with {1} partition failures and {2} insert failures.'.format(len(event['Records']), len(bad_records), len(bad_inserts))
