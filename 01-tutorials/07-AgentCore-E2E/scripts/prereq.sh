#!/bin/sh

# ----- Config -----
BUCKET_NAME=${1:-customersupport112}
INFRA_STACK_NAME=${2:-CustomerSupportStackInfra}
COGNITO_STACK_NAME=${3:-CustomerSupportStackCognito}
INFRA_TEMPLATE_FILE="prerequisite/infrastructure.yaml"
COGNITO_TEMPLATE_FILE="prerequisite/cognito.yaml"
REGION=$(aws configure get region 2>/dev/null || echo "us-west-2")
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FULL_BUCKET_NAME="${BUCKET_NAME}-${ACCOUNT_ID}-${REGION}"
ZIP_FILE="lambda.zip"
LAYER_ZIP_FILE="ddgs-layer.zip"
LAYER_SOURCE="prerequisite/lambda/python"
S3_LAYER_KEY="${LAYER_ZIP_FILE}"
LAMBDA_SRC="prerequisite/lambda/python"
S3_KEY="${ZIP_FILE}"

echo "Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
# ----- 1. Create S3 bucket -----
echo "🪣 Using S3 bucket: $FULL_BUCKET_NAME"
if [ "$REGION" = "us-east-1" ]; then
  aws s3api create-bucket \
    --bucket "$FULL_BUCKET_NAME" \
    2>/dev/null || echo "ℹ️ Bucket may already exist or be owned by you."
else
  aws s3api create-bucket \
    --bucket "$FULL_BUCKET_NAME" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" \
    2>/dev/null || echo "ℹ️ Bucket may already exist or be owned by you."
fi

# ----- 2. Zip Lambda code -----
sudo apt install zip
echo "📦 Zipping contents of $LAMBDA_SRC into $ZIP_FILE..."
cd "$LAMBDA_SRC"
zip -r "../../../$ZIP_FILE" . > /dev/null

cd - > /dev/null

# ----- 3. Upload to S3 -----
echo "☁️ Uploading $ZIP_FILE to s3://$FULL_BUCKET_NAME/$S3_KEY..."
aws s3 cp "$ZIP_FILE" "s3://$FULL_BUCKET_NAME/$S3_KEY"

echo "☁️ Uploading $LAYER_ZIP_FILE to s3://$FULL_BUCKET_NAME/$S3_LAYER_KEY..."
cd "$LAMBDA_SRC"
aws s3 cp "$LAYER_ZIP_FILE" "s3://$FULL_BUCKET_NAME/$S3_LAYER_KEY"
cd - > /dev/null
# ----- 4. Deploy CloudFormation -----
deploy_stack() {
  set +e

  local stack_name=$1
  local template_file=$2
  shift 2
  local params=("$@")

  echo "🚀 Deploying CloudFormation stack: $stack_name"

  output=$(aws cloudformation deploy \
    --stack-name "$stack_name" \
    --template-file "$template_file" \
    --s3-bucket "$FULL_BUCKET_NAME" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    "${params[@]}" 2>&1)

  exit_code=$?

  echo "$output"

  if [ $exit_code -ne 0 ]; then
    if echo "$output" | grep -qi "No changes to deploy"; then
      echo "ℹ️ No updates for stack $stack_name, continuing..."
      return 0
    else
      echo "❌ Error deploying stack $stack_name:"
      echo "$output"
      return $exit_code
    fi
  else
    echo "✅ Stack $stack_name deployed successfully."
    return 0
  fi
}

# ----- Run both stacks -----
echo "🔧 Starting deployment of infrastructure stack with LambdaS3Bucket = $FULL_BUCKET_NAME..."
deploy_stack "$INFRA_STACK_NAME" "$INFRA_TEMPLATE_FILE" --parameter-overrides LambdaS3Bucket="$FULL_BUCKET_NAME" LambdaS3Key="$S3_KEY" LayerS3Key="$S3_LAYER_KEY"
infra_exit_code=$?

echo "🔧 Starting deployment of Cognito stack..."
deploy_stack "$COGNITO_STACK_NAME" "$COGNITO_TEMPLATE_FILE"
cognito_exit_code=$?

echo "✅ Deployment complete."