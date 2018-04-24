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
import json
import csv
import array
import copy
import time
import traceback

endpoint_name = 'tffmpromo-2018-04-10-02-17-05-752'

ad_map = {
    '0f2fcf95319f5c1e5745371351f521e5': "Free Shipping",
    '19754ec121b3a99fff3967646942de67': '10% off',
    '5e378677ca9bb41114562e84001c8516': 'Buy one get one free',
    'be83df9772ec47fd210b28091138ff11': '20% off your next order',
    '3735290a415dc236bacd7ed3aa03b2d5': 'Free shipping on orders over $50',
    '6b989e6ea6d423160c8b30beb8240946': 'Free express shippping',
    '60253e351dee27e77cd50366585517a3': 'Free pair of socks',
    'a5fc37404646ac3d34118489cdbfb341': '20% off any formalwear',
    '3c9af92d575a330167fb61dda93b5783': '20% off any shirt',
    'c5f63750c2b5b0166e55511ee878b7a3': '10% off any accessory',
    '241145334525b9b067b15de4fd7a0df1': 'Buy today and enter a raffle',
    'fe8efbbd8879b615478cf7314b3b87ba': '15% off',
    'ebb77a97cfdfd01c8b2f5cbffb1d5627': 'Buy one get two free',
    '5ac4398e4d8ad4167a57b43e9c724b18': '10% off your next order',
    'ccbdecfb71d4a0a7e836a4a4b1e69c97': 'Free shipping on orders over $100',
    '72d34a12b35de79a46de4fa2298a349b': 'Free overnight shippping',
    '56691dbb7196e6114c95306094239118': 'Free pair of sandals',
    'eb0389774fca117ee06c5c02a6ba76af': '20% off any pants',
    '0c2c89e5fe431aae53fb1ae058770fa2': '10% off any purse',
    '0576e74e809b3b6f04db1fd98c8c9afb': '10% off any wallet'
}

prod_map = {
    'ac26975cf46eae9898b7d906bdfbbf99ce7813ffc3f9b7c42163a55e02e81516': 'Watch',
    '81dc9575e12600c50cca637701215bdf3d923eebcb08cc4c67fd928103c4931a': 'Sunglasses',
    '154f65f908a7406826ed6408a156db1bdb82f8f514dffc9c344dfba31ace8520': 'Bowtie',
    '19e54986c139665f0bc1aee6073618a4dd2cbdbe577a1b51989b2cfd96f43eb3': 'Gloves',
    'ea760083815933f4f181ffd989b03fb5398b127dc194c08e89b2f35edf11f21f': 'Handbag',
    '10698b6475abd54c5c6d1724d6f51cb795234c23a23daf1bdef1886a8ae522b5': 'Socks',
    '6f529242bbc6dfa46a35f7b9d37a32cd11a0838f204c24f95615d29d2d363ada': 'Yellow Shirt',
    '234e511622f9e1377531dd2df04911360b2d90e18af5b9f78dc58e7d605d4136': 'Green Shirt',
    'ff1bd73f19ccc09842c0b0ad14ff0402e91324cdf924aa3a6a39bfd8c2d9acb3': 'Blue Shirt',
    '66863da8db7e6c51bed5eccc89a91f756e4baee85ad4469e15f0a0cc70f7afdb': 'Skirt',
    '26467f203f42913b6bc575fd4adc89ad66c5db082c8ab90cfc7bb3a5ab1b0ddc': 'Black Shirt',
    '458f4e0daefe1808fd738aaa6613ef3d365d44865606f40c56b3fb554b8fd248': 'Cap',
    'eb49b22a1bbd88fbdf614e3494326c3d2dd853104bff8c5adeaa99a143bdf7d2': 'Hat',
    '8497a9dd86ab3b7f192f2e65994b972787bdcdc6b501b48dab19eaa4737ca148': 'Wizard Hat',
    '8bf8f87492a799528235c04bb18ff2d12db5058ff6e9a07041739be984a72df9': 'Jacket',
    '4740b6c83b6e12e423297493f234323ffd1c991f3d4496a71daebbef01d6dcf0': 'Suit',
    'b042951fdb45ddef8ba6075ced0e5885bc2fa4c4470bf790432e606d85032017': 'Ties',
    '21a509189fb0875c3732590121ff3fc86da770b0628c1812e82f023ee2e0f683': 'Sandals',
    'f3c93baa0cf4430849611cedb3a40ec4094d1d370be8417181da5d13ac99ef3d': 'Shoes',
    '0708f809769d6eb4f49d3f6cf6c09e69c754f1337a21b0d5d5a0d0f2c712271e': 'Flip flops'
}

# Kinesis data is base64 encoded so decode here
# userid	offerid	countrycode	category	merchant	utcdate	rating
payload = 'edward,0576e74e809b3b6f04db1fd98c8c9afb,de,100020213,ac26975cf46eae9898b7d906bdfbbf99ce7813ffc3f9b7c42163a55e02e81516,1518318207.8448,1'
print("Decoded payload: " + payload)

fields = payload.split(',')
if len(fields) != 7:
    raise Exception(
        "Expected input with 7 comma delimited fields, but got {0}".format(payload))
user = fields[0]
ad = fields[1]
countrycode = fields[2]
category = fields[3]
product = fields[4]
timestamp = fields[5]
rating = fields[6]
uid = base64.b64encode(user)

# Convert to json
js = {'instances': []}
ad_idx = {}
idx = 0
for adkey in ad_map.keys():
    js['instances'].append({'keys': ["userid","offerid","countrycode","category","product"], 'values': [uid,adkey,countrycode,category,product]})
    ad_idx[str(idx)] = adkey
    idx = idx + 1
model_input = json.dumps(js)
print(model_input)

# invoke model
client = boto3.client('sagemaker-runtime')
response = client.invoke_endpoint(
    EndpointName=endpoint_name,
    Body=model_input.encode('utf-8'),
    ContentType='application/json',
    Accept='application/json'
)

res_json = json.loads(response['Body'].read().decode("utf-8"))

print("Got model response {0}".format(res_json))
idx = 0
max_score = -2.0
selected_ad = '0'
for prediction in res_json['predictions']:
    score = prediction['score']
    if score > max_score:
        max_score = score
        selected_ad = ad_idx[str(idx)]
    idx = idx + 1

print("Best response score: {0}".format(max_score))
print("Best ad: {0}".format(selected_ad))
