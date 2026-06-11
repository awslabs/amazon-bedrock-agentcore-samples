export AWS_PAGER=

TIMESTAMP := $(shell date +%Y%m%d%H%M%S)

LOCAL_PORT     ?= 8080
STACK_NAME     ?= icarus-app
INSTANCE_TYPE  ?= t3.medium
REGION         ?= us-west-2
CODE_S3_BUCKET ?= icarus-app-$(TIMESTAMP)
CODE_S3_KEY    ?= app-code.zip

KEY_NAME ?=

AWS_CHECK := $(shell aws sts get-caller-identity --region $(REGION) > /dev/null 2>&1; echo $$?)
ifneq ($(AWS_CHECK),0)
$(error [ERROR] AWS credentials not configured. Run `aws configure` or set AWS environment variables)
endif

.PHONY: package upload deploy status outputs session logs connect delete

package:
	@rm -f app-code.zip

	cd app && zip -r ../app-code.zip . \
		-x "*__pycache__*" \
		-x "*.mypy_cache*" \
		-x "uv.lock" \
		-x "*.venv*" \
		-x "*.git*" \
		-x "*exp/sessions*" \
		-x "*.pyc"

upload: package
	aws s3 ls --region $(REGION) s3://$(CODE_S3_BUCKET) 2>/dev/null || \
	aws s3 mb --region $(REGION) s3://$(CODE_S3_BUCKET)

	aws s3 cp --region $(REGION) app-code.zip s3://$(CODE_S3_BUCKET)/app-code.zip

deploy: upload
	aws cloudformation create-stack \
		--stack-name $(STACK_NAME) \
		--template-body file://cfn.yaml \
		--parameters \
			ParameterKey=KeyName,ParameterValue=$(KEY_NAME) \
			ParameterKey=CodeS3Bucket,ParameterValue=$(CODE_S3_BUCKET) \
			ParameterKey=CodeS3Key,ParameterValue=app-code.zip \
			ParameterKey=InstanceType,ParameterValue=$(INSTANCE_TYPE) \
		--capabilities CAPABILITY_NAMED_IAM \
		--region $(REGION)

	@rm -f app-code.zip

status:
	aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--query 'Stacks[0].StackStatus' \
		--region $(REGION)

wait:
	aws cloudformation wait stack-create-complete \
		--stack-name $(STACK_NAME) \
		--region $(REGION)

outputs:
	aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--query 'Stacks[0].Outputs' \
		--region $(REGION)

logs: ; aws logs tail /aws/ec2/$(STACK_NAME) --follow --region $(REGION)

session:
	@INSTANCE_ID=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--query 'Stacks[0].Outputs[?OutputKey==`InstanceId`].OutputValue' \
		--output text \
		--region $(REGION)) && \
	echo "Starting SSH tunnel (ctrl + c to stop)..." && \
	echo "You can access the web app at http://localhost:$(LOCAL_PORT)" && \
	aws ssm start-session --target $$INSTANCE_ID \
		--document-name AWS-StartPortForwardingSession \
		--parameters '{"portNumber":["8080"],"localPortNumber":["$(LOCAL_PORT)"]}' \
		--region $(REGION)

connect:
	@INSTANCE_ID=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--query 'Stacks[0].Outputs[?OutputKey==`InstanceId`].OutputValue' \
		--output text \
		--region $(REGION)) && \
	aws ssm start-session --target $$INSTANCE_ID --region $(REGION)

delete:
	@BUCKET=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--query 'Stacks[0].Outputs[?OutputKey==`CodeS3Bucket`].OutputValue' \
		--output text \
		--region $(REGION)) && \
	aws s3 rm --region $(REGION) s3://$$BUCKET --recursive && \
	aws s3 rb --region $(REGION) s3://$$BUCKET

	aws cloudformation delete-stack \
		--stack-name $(STACK_NAME) \
		--region $(REGION)
