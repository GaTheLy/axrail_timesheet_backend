# Technology Stack

## Infrastructure
- **AWS CDK**: Infrastructure as Code using Python
- **AWS Services**: CodePipeline, CodeBuild, S3, CloudFront, Cognito, AppSync, DynamoDB, Elasticsearch
- **Python**: CDK application and infrastructure definitions

## Frontend
- **Node.js/npm**: Package management and build system
- **Vite**: Build tool for admin web interface
- **AWS CodeArtifact**: Private npm registry for shared components

## Build System
- **AWS CodePipeline**: CI/CD orchestration
- **AWS CodeBuild**: Build and deployment execution
- **BitBucket**: Source code repositories with CodeStar connections

## Common Commands

### CDK Operations
```bash
# Install dependencies
pip install -r requirements.txt

# Synthesize CloudFormation templates
cdk synth

# List all stacks
cdk ls

# Deploy specific stack
cdk deploy <stack-name>

# Compare deployed vs current state
cdk diff

# Bootstrap CDK (first time setup)
cdk bootstrap
```

### Development Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment (macOS/Linux)
source .venv/bin/activate

# Activate virtual environment (Windows)
.venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### Testing
```bash
# Run unit tests
pytest
```

## Environment Configuration
- Multi-environment support: dev, staging, prod
- Environment-specific configurations in `environment.py`
- Cross-account deployment using assumed roles