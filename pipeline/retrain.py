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
import sys
import math
import json
import time
from pyspark import SparkContext, SparkConf

from pyspark.mllib.evaluation import MulticlassMetrics
from pyspark.mllib.evaluation import BinaryClassificationMetrics

import pyspark.sql.functions as F
from pyspark.sql.functions import col, round, explode, desc

import pyspark.sql.types as T
from pyspark.sql.types import StructType, StringType, IntegerType, StructField, DoubleType, ArrayType
from pyspark.sql import SparkSession

from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler

from sagemaker_pyspark import IAMRole, classpath_jars, SageMakerEstimator
from sagemaker_pyspark.transformation.serializers.serializers import ProtobufRequestRowSerializer
from sagemaker_pyspark.transformation.deserializers.deserializers import ProtobufResponseRowDeserializer
from sagemaker_pyspark.transformation.deserializers.deserializers import LinearLearnerRegressorProtobufResponseRowDeserializer

def read_unprocessed_partitions(spark, s3_path):
    dfUnProc = spark.read.option("multiline", "true").json("{0}/{1}".format(s3_path, "unprocessed.json"))
    dfItems = dfUnProc.withColumn("Items", explode(dfUnProc.Items))
    dfPartitions = dfItems.select(col("Items.File.S").alias("file"),col("Items.IsProcessed.N").alias("processed"),col("Items.Stream.S").alias("stream"))
    return dfPartitions

def read_click_partitions(spark, dfInput):

    schema = StructType([
        StructField("userid", StringType()),
        StructField("offerid", StringType()),
        StructField("countrycode", StringType()),
        StructField("category", StringType()),
        StructField("product", StringType()),
        StructField("timestamp", StringType()),
        StructField("label", StringType())
    ])

    clicksDf = None
    for s3file in dfInput.rdd.collect():
        path = "s3://{0}".format(s3file.file)
        if clicksDf == None:
            clicksDf = spark.read.csv(
                path, header=False, mode="DROPMALFORMED", schema=schema
            )
        else:
            dfLocal = spark.read.csv(
                path, header=False, mode="DROPMALFORMED", schema=schema
            )
            clicksDf = clicksDf.union(dfLocal)

    return clicksDf

def one_hot_encode(dfFull):

    dfNoNullNumbers = dfFull.fillna('0')

    # start with user id
    stringIndexer_user = StringIndexer(inputCol="userid", outputCol="UserIdx", handleInvalid='keep')
    model_user = stringIndexer_user.fit(dfNoNullNumbers)
    indexed_user = model_user.transform(dfNoNullNumbers)

    encoder_user = OneHotEncoder(inputCol="UserIdx", outputCol="UserVec")
    encoded_user = encoder_user.transform(indexed_user)
    
    # now do item
    stringIndexer_item = StringIndexer(inputCol="product", outputCol="ItemIdx", handleInvalid='keep')
    model_item = stringIndexer_item.fit(encoded_user)
    indexed_item = model_item.transform(encoded_user)

    encoder_item = OneHotEncoder(inputCol="ItemIdx", outputCol="ItemVec")
    encoded_item = encoder_item.transform(indexed_item)

    # now do category
    stringIndexer_cat = StringIndexer(inputCol="category", outputCol="CategoryCleanedIdx", handleInvalid='keep')
    model_cat = stringIndexer_cat.fit(encoded_item)
    indexed_cat = model_cat.transform(encoded_item)

    encoder_cat = OneHotEncoder(inputCol="CategoryCleanedIdx", outputCol="CategoryCleanedVec")
    encoded_cat = encoder_cat.transform(indexed_cat)

    # now do offerid
    stringIndexer_offer = StringIndexer(inputCol="offerid", outputCol="OfferIdx", handleInvalid='keep')
    model_offer = stringIndexer_offer.fit(encoded_cat)
    indexed_offer = model_offer.transform(encoded_cat)

    encoder_offer = OneHotEncoder(inputCol="OfferIdx", outputCol="OfferVec")
    encoded_offer = encoder_offer.transform(indexed_offer)

    # now do countrycode
    stringIndexer_cc = StringIndexer(inputCol="countrycode", outputCol="CcIdx", handleInvalid='keep')
    model_cc = stringIndexer_cc.fit(encoded_offer)
    indexed_cc = model_cc.transform(encoded_offer)

    encoder_cc = OneHotEncoder(inputCol="CcIdx", outputCol="CcVec")
    encoded_cc = encoder_cc.transform(indexed_cc)

    dfEncoded = encoded_cc.drop('userid').drop('UserIdx') \
        .drop('product').drop('ItemIdx') \
        .drop('offerid').drop('OfferIdx') \
        .drop('countrycode').drop('CcIdx') \
        .drop('category').drop('CategoryCleanedIdx') 

    return dfEncoded

def train_tffm(roleArn, image_uri, header_file_bucket, header_file_prefix, train_instance_type, endpoint_instance_type, train_df):

    estimator = SageMakerEstimator(
        trainingImage = image_uri,
        modelImage = image_uri,
        trainingInstanceType = train_instance_type,
        trainingInstanceCount = 1,
        endpointInstanceType = endpoint_instance_type,
        endpointInitialInstanceCount = 1,
        requestRowSerializer = ProtobufRequestRowSerializer(),
        responseRowDeserializer = LinearLearnerRegressorProtobufResponseRowDeserializer(),
        hyperParameters = {"order": "3", "rank": "7", "epochs": "50", "header_file_bucket": header_file_bucket, "header_file_prefix": header_file_prefix },
        trainingInstanceVolumeSizeInGB = 1024,
        trainingSparkDataFormat='sagemaker',
        sagemakerRole=IAMRole(roleArn)
        )

    model = estimator.fit(train_df)
    return model

def validate_tffm(spark, sc, model, test_df, s3_metrics_path, s3_endpoint_path):
    # get predictions
    validation_df = model.transform(test_df)
    
    metricsSchema = StructType() \
        .add("metric", StringType()) \
        .add("value", DoubleType())
    metrics_names = []

    # apply threshold
    def thresholdScore(x):
        retval = 0.0
        if x > 0.5:
            retval = 1.0
        return retval
    
    thresholdScoreUdf = F.UserDefinedFunction(thresholdScore, T.FloatType())
    
    validation_df_round = validation_df.withColumn('rscore', thresholdScoreUdf(validation_df.score)) 
    predTffm = validation_df_round.select(['label','rscore'])

    predictionAndLabelsTffm = predTffm.rdd.map(lambda lp: (lp.rscore, lp.label))
    metricsTffm = BinaryClassificationMetrics(predictionAndLabelsTffm)

    metrics_names.append(("Area_under_PR",metricsTffm.areaUnderPR))
    metrics_names.append(("Area_under_ROC",metricsTffm.areaUnderROC))

    mmetricsTffm = MulticlassMetrics(predictionAndLabelsTffm)
    metrics_names.append(("Precision",mmetricsTffm.precision()))
    metrics_names.append(("Recall",mmetricsTffm.recall()))
    metrics_names.append(("F1",mmetricsTffm.fMeasure()))
    metrics_names.append(("Weighted_recall",mmetricsTffm.weightedRecall))
    metrics_names.append(("Weighted_precision",mmetricsTffm.weightedPrecision))
    metrics_names.append(("Weighted_F1",mmetricsTffm.weightedFMeasure()))
    metrics_names.append(("Weighted_F05",mmetricsTffm.weightedFMeasure(beta=0.5)))
    metrics_names.append(("Weighted_FP_rate",mmetricsTffm.weightedFalsePositiveRate))

    mRdd = sc.parallelize(metrics_names).coalesce(1)
    dfMetrics = spark.createDataFrame(mRdd, metricsSchema)
    dfMetrics.write.csv("{0}/{1}".format(s3_metrics_path, model.endpointName), mode="overwrite")

    endpointSchema = StructType() \
        .add("time", StringType()) \
        .add("endpoint", StringType())
    endpoint_name = []
    endpoint_name.append((str(time.time()),str(model.endpointName)))
    eRdd = sc.parallelize(endpoint_name).coalesce(1)
    dfEndpoint = spark.createDataFrame(eRdd, endpointSchema)
    dfEndpoint.write.csv("{0}/endpoint.txt".format(s3_endpoint_path), mode="overwrite")

def prepare_features(dfEncoded):

    # drop unused columns
    dfLabeled = dfEncoded.withColumn("dlabel", dfEncoded["label"].cast(DoubleType())).drop("label")
    dfLabeled = dfLabeled.withColumnRenamed("dlabel", "label")
    dfLabeled = dfLabeled.withColumnRenamed("UserVec", "userid") \
        .withColumnRenamed("ItemVec", "product") \
        .withColumnRenamed("OfferVec", "offerid") \
        .withColumnRenamed("CcVec", "countrycode") \
        .withColumnRenamed("CategoryCleanedVec", "category") 

    # assemble into feature vector
    ignore = ['label']
    assembler = VectorAssembler(
        inputCols=[x for x in dfLabeled.columns if x not in ignore],
        outputCol='features')
    dfFeatures = assembler.transform(dfLabeled)
    dfReadyForModel = dfFeatures.drop('userid').drop('product').drop('category').drop('countrycode').drop('offerid')

    return dfReadyForModel

def save_lookups(spark, dfReadyForModel, s3_header_path):
    lookupSchema = StructType() \
        .add("name", StringType()) \
        .add("idx", IntegerType())
  
    lookup = dfReadyForModel.schema["features"].metadata["ml_attr"]["attrs"]
    lookup_names = []
    for colentry in lookup['binary']:
        lookup_names.append((colentry['name'],colentry['idx']))

    lRdd = sc.parallelize(lookup_names)
    dfLookup = spark.createDataFrame(lRdd, lookupSchema)
    dfLookup.write.csv(s3_header_path, mode="overwrite")

if __name__ == "__main__":
    if len(sys.argv) != 7:
        print("Usage: retrain clickstream_name role_arn image_uri input_bucket output_bucket ref_bucket", file=sys.stderr)
        exit(-1)

    s3_input_bucket = sys.argv[4]
    s3_output_bucket = sys.argv[5]
    s3_ref_bucket = sys.argv[6]
    header_file_bucket = s3_input_bucket 
    header_file_prefix = "headers/headers.csv" 
    s3_path = "s3://{0}/ddb-out".format(s3_ref_bucket) 
    s3_merged_path = "s3://{0}/merged.parquet".format(s3_input_bucket) 
    s3_header_path = "s3://{0}/{1}".format(header_file_bucket, header_file_prefix) 
    s3_metrics_path = "s3://{0}/metrics".format(s3_output_bucket) 
    s3_endpoint_path = "s3://{0}/endpoint".format(s3_output_bucket) 
    roleArn = sys.argv[2] 
    image_uri = sys.argv[3] 
    train_instance_type = "ml.c4.8xlarge"
    endpoint_instance_type = "ml.m4.xlarge"
    clickstream_name = sys.argv[1] 

    sc = SparkContext(appName="AdRecRetrain")
    spark = SparkSession.builder.getOrCreate()

    # read the input list of unprocessed partitions 
    print("Reading input list of files")
    dfPartitions = read_unprocessed_partitions(spark, s3_path)

    # retain only unprocessed partitions
    clicksDfPartition = dfPartitions.filter(dfPartitions.processed == '0')

    # load the actual click data
    print("Loading data")
    clicksDf = read_click_partitions(spark, clicksDfPartition)

    # drop timestamp
    prunedClicks = clicksDf.drop('timestamp')

    # write merged data
    print("Writing parquet data")
    prunedClicks.write \
        .format("parquet") \
        .mode("append") \
        .option("compression", "gzip") \
        .save(s3_merged_path)
    
    # read full data set
    print("Reading full parquet data")
    dfFull = spark.read.parquet(s3_merged_path)

    # one hot encode
    print("Encoding")
    dfEncoded = one_hot_encode(dfFull)

    # transform into feature vector for ML
    print("Preparing features")
    dfReadyForModel = prepare_features(dfEncoded)

    # save lookup table
    print("Saving lookup table")
    save_lookups(spark, dfReadyForModel, s3_header_path)    

    # train model
    print("Training model")
    train_df, test_df = dfReadyForModel.randomSplit([0.8, 0.2])
    model = train_tffm(roleArn, image_uri, header_file_bucket, header_file_prefix, train_instance_type, endpoint_instance_type, train_df)
    print("Validating model")
    validate_tffm(spark, sc, model, test_df, s3_metrics_path, s3_endpoint_path)

    print("Done")
    sc.stop()
