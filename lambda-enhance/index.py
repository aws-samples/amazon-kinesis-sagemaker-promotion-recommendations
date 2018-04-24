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

def handler(event, context):
    bad_records = []
    for record in event['Records']:
        # Kinesis data is base64 encoded so decode here
        payload = base64.b64decode(record['kinesis']['data'])
        print("Decoded payload: " + payload)

        # Each line is a CSV in format: userid	offerid	countrycode	category	merchant	utcdate	rating
        # 'edward' c5f63750c2b5b0166e55511ee878b7a3	de	100020213	f3c93baa0cf4430849611cedb3a40ec4094d1d370be8417181da5d13ac99ef3d	2016-06-14 17:28:47.0	0
        fields = payload.split(',')
        if len(fields) != 7:
            bad_records.append(payload)
            print("Invalid record (need 7 fields): {0}".format(payload))
            continue
        user = fields[0]
        ad = fields[1]
        countrycode = fields[2]
        category = fields[3]
        product = fields[4]
        timestamp = fields[5]
        rating = fields[6]

        # Translate user name to an encoded ID.  We'll just use a simple encoding here.
        uid = base64.b64encode(user)

        # publish to firehose
        fhclient = boto3.client('firehose')
        fhrecord = "{0},{1},{2},{3},{4},{5},{6}\n".format(uid, ad, countrycode, category, product, timestamp, rating)
        fhresponse = fhclient.put_record(
            DeliveryStreamName=os.environ['DeliveryStreamName'],
            Record={
                'Data': fhrecord.encode('utf-8')
            }
        )
        print("Response from Firehose: {0}".format(fhresponse))
    return 'Processed {0} records, with {1} failures.'.format(len(event['Records']), len(bad_records))
