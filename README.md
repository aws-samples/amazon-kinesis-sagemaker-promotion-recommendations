# Promotion Recommendation System using Kinesis and SageMaker

This repository has a set of CloudFormation templates, scripts, and
other material for setting up a low-latency recommendation system
for promotions.

For background on the use case, see the accompanying blog post.

## License Summary

This sample code is made available under a modified MIT license. See the LICENSE file.

## Copyright notice

    Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
    
    Permission is hereby granted, free of charge, to any person obtaining a copy of this
    software and associated documentation files (the "Software"), to deal in the Software
    without restriction, including without limitation the rights to use, copy, modify,
    merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so.
    
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
    INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
    PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
    OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Sources

This example uses sample code from:

* [SciKit bring your own](https://github.com/awslabs/amazon-sagemaker-examples/tree/master/advanced_functionality/scikit_bring_your_own)
* Bootstrap JS 2.2
* [eb-php-demo-simple-app](https://github.com/aws-samples/eb-demo-php-simple-app)

The sample data set is the [KASANDR](https://archive.ics.uci.edu/ml/datasets/KASANDR#) data set from the
UCI Machine Learning Repository.  Credit goes to:

    Sumit Sidana, Charlotte Laclau, Massih-Reza Amini, Gilles Vandelle, and Andre Bois-Crettez. 'KASANDR: A Large-Scale Dataset with Implicit Feedback for Recommendation', SIGIR 2017. 

## Setup

This system uses several AWS services to deploy a recommendation system
with an end-to-end data pipeline covering the full data lifecycle from
ingest through to nightly model training.

There are several steps involved in deploying this system.

* Verify that all prerequisites are satisfied.
* Download the repository to your machine
* Upload data to an initial S3 bucket.
* Deploy the initial SageMaker endpoint.
* Edit the scripts `create.sh` and `update.sh`.  There are several parameters in these scripts that you should modify to suit your preferences.  We will describe these parameters in detail later on.
* Deploy the CloudFormation (CFN) templates.
* Retrain the system with the full data set.

Be aware that deploying this system will incur charges in your AWS account.

### Prerequisites

You will need to deploy this system in a region that has access to the following AWS
services:

* SageMaker
* Glue
* Kinesis
* Data Pipeline
* S3
* Lambda
* IAM
* KMS
* CloudWatch
* DynamoDB
* EMR
* SNS

We tested this system in `us-east-1` and `us-west-2`.

You should have the AWS CLI installed and configured.  

### Download repository

Use GitHub or your preferred Git client software to download this repository.  We will
refer to the repository location on your machine as `working-dir`.

### Upload data

Create a new S3 bucket in your account with versioning enabled.  We will refer to this bucket as
`bucket-dataprep`.  

    aws s3 mb s3://bucket-dataprep

Now upload the repository to this bucket.

    aws s3 sync working-dir s3://bucket-dataprep/repo

We bootstrap the machine learning model with this public data set:  

* [KASANDR](https://archive.ics.uci.edu/ml/datasets/KASANDR#)

Download this data set and upload it to the data preparation bucket.  

    mkdir data
    cd data
    wget https://archive.ics.uci.edu/ml/machine-learning-databases/00385/de.tar.bz2

Expand this archive.  You will see two files in the `de` folder, `test_de.csv` and `train_de.csv`.

Now upload the data sets to S3.

    aws s3 cp de/train_de.csv s3://bucket-dataprep/data/train_de.csv
    aws s3 cp de/test_de.csv  s3://bucket-dataprep/data/test_de.csv

### Initial SageMaker endpoint

The Kasandr data set is too large to use on a single notebook instance, but
it is possible to use a subset of the data in a notebook.  We'll start by bootstrapping
a model using a small data set and an interactive notebook.  

Since this is a one-time process, we'll just do this with a training Jupyter notebook.

* Create a SageMaker notebook instance of type `ml.m4.16xlarge`
    * Create a role for Sagemaker.  It needs access to  Elastic Container Registry (ECR), the Sagemaker service, and any S3 buckets used for this project.
    * Add tags for cost allocation as desired
* Install extra python modules on the training instance.
    * Open a terminal on the notebook instance.
    * Activate the Python environment: `source activate python2` 
    * Use Pip: `pip install tffm tensorflow sagemaker --upgrade`
* The notebook `data-xplor-tffm` shows a start-to-finish training session that doesn't directly use SageMaker.  It's useful for experimenting with TFFM.  This notebook loads the original data, converts part of it to protobuf format, and calls TFFM directly.  It also saves a subset of the data for future use.  
    * You will need to change the name of the bucket containing the reference data.  Search for the line `bucket = 'promo-dataprep'`, which is on line 2 in the second code block.
    * This notebook assumes it can find the input click data in the reference data bucket.
    * This notebook also has the most detailed explanation of the data format and applied transformations.
    * This notebook saves training data in Protobuf format and headers in CSV format into the `bucket-dataprep` bucket.
* Build and push Sagemaker image: `cd sagemaker-image; ./build_and_push.sh tffmpromo; cd ..`.  Capture the container image URL from the output.
* Run notebook `data-train-tffm` to train the model using SageMaker.  
    * You will need to change the name of the bucket containing the reference data.  Search for the line `bucket = 'promo-dataprep'`, which is on line 2 in the second code block.
    * Insert the URL for the Sagemaker image on line 4 of the fourth code block, in the `containers` map.
    * This notebook will also create an endpoint useful for testing the model.   Be sure to note the endpoint name.

Make sure you are using the `conda_python2` kernel in the notebooks.

### Input parameters for CFN

The `create.sh` and `update.sh` scripts have several input parameters embedded.  Review and tailor these to suit your account.

* S3 buckets
    * `PrepBucketName` - The data preparation bucket you created earlier, `bucket-dataprep`.  This bucket will contain our scripts, reference data sets, and other information.
    - `RawBucketName` - Contains raw clickstream data
    - `EnhancedClickstreamBucketName` - Contains enriched clickstream data
    - `AdLogBucketName` - Contains data about promotion serving activity
    - `ModelTrainingBucketName` - Contains merged data for model training
    - `ModelOutputBucketName` - Contains model output (headers and scoring)
* Kinesis configuration
    * `ShardCount` - number of shards to use for the kinesis streams
* Network parameters
    * `vpccidr` - CIDR to use for the VPC
    * `AllowedCidrIngress` specifies the CIDR that the security groups will allow access from.  The default is `0.0.0.0/0`, but that is very insecure.  You should set this to a CIDR on your own network.
    * `AppPrivateCIDRA`, `AppPrivateCIDRB`, `AppPublicCIDRA`, `AppPublicCIDRB` - CIDR ranges for the two private and two public subnets
* Application configuration
    * `MinSize`, `MaxSize` - limits on the autoscaling group for the application
    * `DesiredCapacity` - normal size of the application cluster
    * `InstanceSize` - instance type to use for the application
    * `keyname` - SSH key to use for instance SSH access
* EMR configuration (used for the EMR cluster created for manual testing purposes)
    * `MaxEmrCapacity`, `MinEmrCapacity` - sets limits on the cluster size
    * `DesiredEmrCapacity` - initial cluster size
    * `EmrCoreInstanceType`, `EmrMasterInstanceType` - instance types to use for the EMR cluster.  Make sure to pick instances that are powerful enough to run the training jobs, and make sure that your account won't bump into any capacity limits on these instance types.
    * `EmrLogDir` - S3 bucket to use for storing EMR logs
    * `emrReleaseLabel` - EMR release to use
* Sagemaker configuration
    * `EndpointName` - Sagemaker endpoint created from the `data-train-tffm` notebook.  The endpoint will be updated automatically as new training jobs are run in the nightly retraining pipeline.
    * `SagemakerImageUri` - URI for the Sagemaker training image created in the previous section.
    * `SagemakerRoleArn` - ARN for the role you use for Sagemaker.
* Metadata catalog configuration
    * `GlueDbName` - Name of the database in the Glue catalog
    * `GlueTableNameEnhClicks`, `GlueTableNameRawClicks`, `GlueTableNameAds` - Table names in the Glue catalog
* Other configuration
    * `ProjectTag` - Tag applied to resources for tracking and cost allocation
    * `LambdaZipVersion`, `LambdaZipVersionEnh`, `LambdaZipVersionEnhBuy`, `LambdaZipVersionPart` - Object version ID for the zip file containing the lambda functions.  These are normally populated automatically by the helper scripts.

### CFN

Deploying the CFN templates will take approximately 30 minutes.

* Run `scripts/zip-lambda.sh bucket-dataprep` to generate the zip files containing the lambda function code.
* Run `scripts/zip-php.sh bucket-dataprep` to generate the zip file containing the PHP app code.
* Set the model endpoint and other parameters in `scripts/create.sh` and `scripts/update.sh`.
* Run the Cloud Formation templates with `scripts/create.sh` or `scripts/update.sh` to deploy the analytics stack.

You can use the script `scripts/status.sh` to check on the status of a CFN deployment.
You can also use the script `scripts/verify.sh` to see if the CFN template passes syntax checks.

### Training with the full data set

Next, we'll train the model using the full data in PySpark. The CFN templates create a long-lived EMR cluster for exploratory use.  

* Go to the EMR console, select the cluster created by CFN, set up an SSH tunnel, and then open Zeppelin.
* Run notebook `FullConvert` to convert the sample data into parquet, and store it in our model input bucket.  You'll need to enter the proper bucket names at the top of the first code block.
* Run notebook `FullTrain` to train the initial model on the full data set.  You can also experiment with the regular FM algorithm in this notebook.  You'll need to enter the proper bucket names, Sagemaker role ARN, and image URI at the top of the first code block.
* Note down the endpoint created during execution of the `FullTrain` notebook.  
* Update the model endpoint in `update.sh` so that you don't accidentally reset it later.

Now you can activate the data pipeline for retraining purposes.  You can run it on a schedule or manually.

You can invoke the latest endpoint for testing using the script `scripts/invoke_ml.py`.  It requires 
setting the endpoint name on line 27.

## Using the system

You can invoke the recommendation system in two ways.  First, you can browse to the 
mock ecommerce application by following the link in the CFN output.  

Second, you can use the script `scripts/generator.py` to write events directly into the 
web application log files, where the Kinesis agent will pick them up.

* SSH to the jump host and then to the web application server.  
* Install the python module `numpy`.
* Run `python generator.py 500 20 /var/www/logs/log_sample.txt 35`.  You can run the script without arguments to see the usage format.

If you want to receive email notifications with promotion recommendations, subscribe to the SNS topic described in the stack output.

After creating some click events through the web application or using the `generatory.py` script,
you should see data flowing through the system into the rest of the S3 buckets.  The script
`scripts/partitions.sh` will show what partitions have been created in the S3 buckets and recorded
in the Glue catalog.  (If you have changed the default Glue database and table names, adjust them in the script as well.)

If you have subscribed to the SNS topic, you'll receive email or SMS notifications.  You can also check out the 
business and operational dashboards.

### BI dashboard

You can set up a business intelligence dashboard using QuickSight or another tool of your choice.  
We include a sample Shiny dashboard that you can launch using RStudio.  It demonstrates how to 
query using standard JDBC connections.  The dashboard is in `dashboard/app.R`, and requires several
variables to be modified, notably the name of the Athena staging bucket and the AWS region.

### Operational dashboard

See the dashboard `AdRecDashboard-<stack name>` in CloudWatch.  It shows several useful metrics
including volume of data stored, Kinesis stream latency, and so on.

### More details on SageMaker

Our model uses a field-aware factorization machine, TFFM.  

When the model performs inference, it needs to know the row and column
indices for each value.  The row index is just the index of the record.
The column index is the index of a particular feature in the original
sparse matrix used for training.

This information is not stored in the protobuf used for training, so the 
process that creates the protobuf from the raw input must also save a lookup
table that gives us the index for each feature.  

The training input to the model will be:

* sparse protobuf file in 'train' channel  
* Location of header CSV file given in hyperparameters
* (Optional) sparse protobuf file in 'test' channel

The training output of the model will be:

* Saved model state
* Header lookup CSV 

The inference input to the model will be:

* JSON list of key-value pairs for each record
* OR, protobuf file

The inference output of the model will be:

* Regression score for each record in JSON or Protobuf format

You can test the Sagemaker image using the scripts in the `sagemaker-image/local_test` folder.

## Python modules

If you want to set up a new python environment for local experimentation, you should 
install the following modules.

* pip install pandas
* pip install scipy
* pip install scikit-learn
* pip install tensorflow
* pip install tffm
* pip install sagemaker

## Limitations

* Does not handle duplicate records in the Kinesis stream.
* Need to manually add your private key to the jump host
* Does not delete old endpoints
* If you run out of memory during a Spark job, increase the `spark.executor.memory` setting in Zeppelin.

## Possible improvements

We could make numerous improvements to this example.  

### Model improvements

We created the model using a sample data set that was not complete.  We had to generate ads and user profiles.
As a result, the model would not perform well in a real environment.  However, the goal of this project is to
demonstrate the mechanics involved in model building, training, and retraining with a nightly pipeline.

### Hot spot detection

Currently we're storing the clickstream data in S3 for use with machine learning and ad-hoc queries.  But we could use it for real-time detection of interesting customer activity on the site.  Kinesis Analytics offers built-in [hot-spot detection](https://docs.aws.amazon.com/kinesisanalytics/latest/dev/app-hotspots-detection.html).  

### Lambda function versioning

Whenever we make a change to a lambda function, we're uploading a new zip file to S3 and reconfiguring the Lambda function to use that new version.  We should also establish a function version and alias for better traceability of code changes and ease of rollback. 

Using versions is particularly important when we update the SageMaker endpoint environment variable for the lambda function that responds to customer activity on the site.  If the new model doesn't work well, we'd like to be able to quickly roll back to the earlier version.

### Align to more recent AWS Solution Guide

A new [AWS Solution for Real Time Web Analytics](https://aws.amazon.com/answers/web-applications/real-time-web-analytics-with-kinesis/) 
offers a different approach to capturing clickstream data for web analytics.  The solution uses client-side code to log click events 
into the web servers, and uses Kinesis Analytics for a real-time graph of customer activity and anomaly detection.  Much of the
basic data pipeline is similar, and perhaps the two approaches can be merged to add the promotion recommendation system.
