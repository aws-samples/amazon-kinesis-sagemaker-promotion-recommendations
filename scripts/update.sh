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

refbucket=$1
stackname=$2
region=$3
SCRIPTDIR=`dirname $0`
if [ "$refbucket" == "" ]
then
    echo "Usage: $0 <dataprep bucket> <stack name> <region>"
    exit 1
fi
if [ "$stackname" == "" ]
then
    echo "Usage: $0 <dataprep bucket> <stack name> <region>"
    exit 1
fi
if [ "$region" == "" ]
then
    echo "Usage: $0 <dataprep bucket> <stack name> <region>"
    exit 1
fi

# Check if we need to append region to S3 URL
TEMPLATE_URL=https://s3.amazonaws.com/$refbucket/repo/cfn/master.yaml
if [ "$region" != "us-east-1" ]
then
    TEMPLATE_URL=https://s3-$region.amazonaws.com/$refbucket/repo/cfn/master.yaml
fi

echo "Synchronizing CFN"
aws s3 sync $SCRIPTDIR/../cfn s3://$refbucket/repo/cfn

echo "Reading object version of lambda zips"
LAMBDA_ZIP=`cat latest_zip.txt`
LAMBDA_ZIP_ENH=`cat latest_zip_enhance.txt`
LAMBDA_ZIP_PART=`cat latest_zip_part.txt`
aws cloudformation update-stack --stack-name $stackname \
    --template-url $TEMPLATE_URL \
    --parameters \
    ParameterKey=RawBucketName,ParameterValue=promo-raw-clicks \
    ParameterKey=PrepBucketName,ParameterValue=promo-dataprep \
    ParameterKey=EnhancedClickstreamBucketName,ParameterValue=promo-enhanced-clicks \
    ParameterKey=AdLogBucketName,ParameterValue=promo-ads \
    ParameterKey=ModelTrainingBucketName,ParameterValue=promo-model-train-input \
    ParameterKey=ModelOutputBucketName,ParameterValue=promo-model-output \
    ParameterKey=ShardCount,ParameterValue=2 \
    ParameterKey=ProjectTag,ParameterValue=PromoBlog \
    ParameterKey=MinSize,ParameterValue=1 \
    ParameterKey=MaxSize,ParameterValue=2 \
    ParameterKey=DesiredCapacity,ParameterValue=1 \
    ParameterKey=InstanceSize,ParameterValue=t2.large \
    ParameterKey=vpccidr,ParameterValue="10.20.0.0/16" \
    ParameterKey=AllowedCidrIngress,ParameterValue="0.0.0.0/0" \
    ParameterKey=AppPrivateCIDRA,ParameterValue="10.20.3.0/24" \
    ParameterKey=AppPrivateCIDRB,ParameterValue="10.20.4.0/24" \
    ParameterKey=AppPublicCIDRA,ParameterValue="10.20.1.0/24" \
    ParameterKey=AppPublicCIDRB,ParameterValue="10.20.2.0/24" \
    ParameterKey=keyname,ParameterValue=key \
    ParameterKey=EndpointName,ParameterValue=endpoint-c0fe08c6e78e-2018-04-11T12-57-38-681 \
    ParameterKey=LambdaZipVersion,ParameterValue="$LAMBDA_ZIP" \
    ParameterKey=LambdaZipVersionEnh,ParameterValue="$LAMBDA_ZIP_ENH" \
    ParameterKey=LambdaZipVersionPart,ParameterValue="$LAMBDA_ZIP_PART" \
    ParameterKey=GlueDbName,ParameterValue="promodb" \
    ParameterKey=GlueTableNameEnhClicks,ParameterValue="ecclicksenh" \
    ParameterKey=GlueTableNameRawClicks,ParameterValue="ecclicksraw" \
    ParameterKey=GlueTableNameAds,ParameterValue="ecadserve" \
    ParameterKey=MaxEmrCapacity,ParameterValue="5" \
    ParameterKey=MinEmrCapacity,ParameterValue="2" \
    ParameterKey=DesiredEmrCapacity,ParameterValue="4" \
    ParameterKey=EmrCoreInstanceType,ParameterValue="r3.2xlarge" \
    ParameterKey=EmrMasterInstanceType,ParameterValue="m4.2xlarge" \
    ParameterKey=EmrLogDir,ParameterValue="s3://promo-dataprep/logs" \
    ParameterKey=emrReleaseLabel,ParameterValue="emr-5.13.0" \
    ParameterKey=SagemakerImageUri,ParameterValue="dkr.ecr.us-east-1.amazonaws.com/tffmpromo:latest" \
    ParameterKey=SagemakerRoleArn,ParameterValue="arn:aws:iam::acct:role/service-role/AmazonSageMaker-ExecutionRole-20180105T085657" \
    --tags Key=Project,Value=PromoBlog \
    --no-use-previous-template \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
