#!/bin/bash

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

region=$1
if [ "$region" == "" ]
then
    echo "Usage: $0 <region> <output bucket> <function name> <ref bucket> <table name> <stream name> <sns topic ARN>"
    exit 1
fi
outputbucket=$2
if [ "$outputbucket" == "" ]
then
    echo "Usage: $0 <region> <output bucket> <function name> <ref bucket> <table name> <stream name> <sns topic ARN>"
    exit 1
fi
fnname=$3
if [ "$fnname" == "" ]
then
    echo "Usage: $0 <region> <output bucket> <function name> <ref bucket> <table name> <stream name> <sns topic ARN>"
    exit 1
fi
refbucket=$4
if [ "$refbucket" == "" ]
then
    echo "Usage: $0 <region> <output bucket> <function name> <ref bucket> <table name> <stream name> <sns topic ARN>"
    exit 1
fi
tblname=$5
if [ "$tblname" == "" ]
then
    echo "Usage: $0 <region> <output bucket> <function name> <ref bucket> <table name> <stream name> <sns topic ARN>"
    exit 1
fi
streamname=$6
if [ "$streamname" == "" ]
then
    echo "Usage: $0 <region> <output bucket> <function name> <ref bucket> <table name> <stream name> <sns topic ARN>"
    exit 1
fi
snstopic=$7
if [ "$snstopic" == "" ]
then
    echo "Usage: $0 <region> <output bucket> <function name> <ref bucket> <table name> <stream name> <sns topic ARN>"
    exit 1
fi

echo Updating AWS CLI
sudo yum -y update aws-cli

echo Updating endpoint for ML function
aws --region $region s3 sync s3://$outputbucket/endpoint/endpoint.txt/ /tmp/endpoints
ENDPOINT=`cat /tmp/endpoints/*.csv | awk -F , '{print $2}'`
aws --region $region lambda update-function-configuration --function-name $fnname --environment '{"Variables":{"DeliveryStreamName":"'$streamname'","EndpointName":"'$ENDPOINT'","SnsTopic":"'$snstopic'"}}'

echo Updating items in DynamoDB
sudo /usr/bin/pip install boto3
cat >/tmp/update-dynamo.py <<EOL
import json
import boto3
import os
import traceback
import sys

client = boto3.client('dynamodb', region_name='$region')
table_name = '$tblname'

input_data = open(sys.argv[1], 'r').read()
json_data = json.loads(input_data)
del_req = {table_name: []}
for item in json_data['Items']:
    f = item['File']['S']
    ip = item['IsProcessed']['N']
    del_req[table_name].append({'DeleteRequest': {'Key': {'File': {'S': f,}, 'IsProcessed': {'N': ip,},},},})

response = client.batch_write_item( RequestItems=del_req)
EOL
aws --region $region s3 cp s3://$refbucket/ddb-out/unprocessed.json /tmp
/usr/bin/python /tmp/update-dynamo.py /tmp/unprocessed.json
