#!/bin/bash
# Create IAM role for App Runner to pull from ECR

echo "Creating trust policy..."
cat > /tmp/apprunner-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "build.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

echo "Creating IAM role..."
aws iam create-role \
  --role-name AppRunnerECRAccessRole \
  --assume-role-policy-document file:///tmp/apprunner-trust.json

echo "Attaching ECR access policy..."
aws iam attach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

echo "Waiting 10 seconds for IAM propagation..."
sleep 10

echo "Verifying role..."
aws iam get-role --role-name AppRunnerECRAccessRole --query 'Role.Arn' --output text

echo "Done. Use the ARN above in your App Runner create-service command."
