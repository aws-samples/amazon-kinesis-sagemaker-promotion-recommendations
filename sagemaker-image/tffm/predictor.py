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

# This file implements a SageMaker model predictor using TFFM.
# As input, it expects either JSON or Protobuf.  
# It returns predictions in the same format as the input.

from __future__ import print_function

import os
import io
import json
import pickle
import StringIO
import sys
import csv
import signal
import traceback

import flask

import pandas as pd
import tensorflow as tf
from tffm import TFFMRegressor
import numpy as np
import scipy.sparse as sp

import sagemaker.amazon.common as smac
from sagemaker.amazon.record_pb2 import Record

prefix = '/opt/ml/'
model_path = os.path.join(prefix, 'model')

# A singleton for holding the model. This simply loads the model and holds it.
# It has a predict function that does a prediction based on the model and the input data.

class ScoringService(object):
    model = None                # Where we keep the model when it's loaded
    num_features = 0
    headers = None

    @classmethod
    def get_headers(cls):
        if cls.headers == None:
            with open(os.path.join(model_path, 'headers.csv'), 'r') as inp:
                cls.headers = [x.strip() for x in inp.readlines()]
        return cls.headers

    @classmethod
    def get_num_features(cls):
        if cls.num_features == 0:
            cls.num_features = len(cls.get_headers())
        return cls.num_features

    @classmethod
    def get_model(cls):
        """Get the model object for this instance, loading it if it's not already loaded."""
        if cls.model == None:
            cls.model = TFFMRegressor(
                 order=3,
                 rank=7,
                 optimizer=tf.train.AdamOptimizer(learning_rate=0.1),
                 n_epochs=50,
                 batch_size=-1,
                 init_std=0.001,
                 input_type='sparse'
             )
            cls.model.core.set_num_features(cls.get_num_features())
            cls.model.load_state(os.path.join(model_path, 'tffm_state.tf'))
            
        return cls.model

    @classmethod
    def predict(cls, input):
        """For the input, do the predictions and return them.

        Args:
            input (numpy array): The data on which to do the predictions. There will be
                one prediction per row in the array"""
        clf = cls.get_model()
        return clf.predict(input)

# The flask app for serving predictions
app = flask.Flask(__name__)

@app.route('/ping', methods=['GET'])
def ping():
    """Determine if the container is working and healthy. In this sample container, we declare
    it healthy if we can load the model successfully."""
    health = ScoringService.get_model() is not None  # You can insert a health check here

    status = 200 if health else 404
    return flask.Response(response='\n', status=status, mimetype='application/json')

@app.route('/invocations', methods=['POST'])
def transformation():
    """Do an inference on a single batch of data. In this server, we take data as JSON, convert
    it to a sparse array for internal use and then convert the predictions back to json.

    Input format is:
    '{"instances": [{"keys": ["User","1","2"], "values": ["a","b","c"]}, {"keys": ["User","5","6"], "values": ["d","e","f"]}]}' 
    """

    # Convert from json to numpy
    te_row_ind = []
    te_col_ind = []
    te_data = []
    te_idx = 0
    headers = ScoringService.get_headers()
    if flask.request.content_type == 'application/json':
        print("Working with JSON input")
        s = flask.request.data.decode('utf-8')
        inputs = json.loads(s)
        for instance in inputs['instances']:

            # The column index has to be found from the headers
            for col_idx in range(0, len(instance['keys'])):
                key = instance['keys'][col_idx]
                val = instance['values'][col_idx]
                item_to_find = "{0}_{1}".format(key, val)
                try:
                    te_col_ind.append(headers.index(item_to_find))
                    te_data.append(1.0)
                    te_row_ind.append(te_idx) 
                except Exception as e:
                    te_col_ind.append(1)
                    te_data.append(0.0)
                    te_row_ind.append(te_idx) 
                    print("Couldn't find header for {0}".format(item_to_find))
            te_idx = te_idx + 1
    elif flask.request.content_type == 'application/x-recordio-protobuf':
        print("Working with Protobuf input")
        #print("{0}".format(flask.request.stream))
        #s = flask.request.data.decode('latin-1')
        #print("Data: {}".format(s))
        test_records = smac.read_records(StringIO.StringIO(flask.request.data))
        num_test_samples = len(test_records)
        for test_record in test_records:
            te_row_ind.extend([te_idx] * len(test_record.features['values'].float32_tensor.values))
            te_col_ind.extend(test_record.features['values'].float32_tensor.keys)
            te_data.extend(test_record.features['values'].float32_tensor.values)
            te_idx = te_idx + 1

    else:
        return flask.Response(response='This predictor only supports JSON or Protobuf data', status=415, mimetype='text/plain')

    X_te_sparse = sp.csr_matrix( (np.array(te_data),(np.array(te_row_ind),np.array(te_col_ind))), shape=(te_idx,ScoringService.get_num_features()) )
    print('Invoked with {} records'.format(X_te_sparse.shape))

    # Do the prediction
    predictions = ScoringService.predict(X_te_sparse)

    # Convert from array back to json
    result = None
    if flask.request.content_type == 'application/json':
        js = {'predictions': []}
        for pred_value in predictions:
            js['predictions'].append({'score': str(pred_value)})
        result = json.dumps(js)
    else:
        # convert to protobuf
        buf = io.BytesIO()
        record = Record()
        for pred_value in predictions:
            record.Clear()
            #smac._write_label_tensor('Float32', record, pred_value)
            record.label["score"].float32_tensor.values.extend([pred_value])
            smac._write_recordio(buf, record.SerializeToString())
        buf.seek(0)
        result = buf.getvalue()

    return flask.Response(response=result, status=200, mimetype=flask.request.content_type)
