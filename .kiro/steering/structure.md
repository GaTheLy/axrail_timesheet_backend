# Project Structure

## Root Directory
```
├── app.py                    # CDK app entry point
├── cdk.json                  # CDK configuration
├── requirements.txt          # Python dependencies
├── requirements-dev.txt      # Development dependencies
└── source.bat               # Windows environment setup
```

## Main Package Structure
```
colabs_pipeline_cdk/
├── environment.py           # Environment configurations and constants
├── pipeline_admin_web_stack.py    # Admin web CI/CD pipeline
├── pipeline_appsync_stack.py      # GraphQL API pipeline
├── pipeline_backend_stack.py      # Backend services pipeline
├── pipeline_dbs_stack.py          # Database infrastructure pipeline
└── pipeline_einvoice_web_stack.py # E-invoice web pipeline
```

## Testing Structure
```
tests/
├── __init__.py
└── unit/
    ├── __init__.py
    └── test_*.py           # Unit test files
```

## Configuration Structure
```
.kiro/
└── steering/               # AI assistant guidance documents
```

## Naming Conventions

### Stack Naming
- Pattern: `{ProjectName}{Component}Stack-{Environment}`
- Example: `ColabsPipelineDBSStack`, `ColabsPipelineAdminWebStack`

### Pipeline Naming
- Pattern: `{projectName.lower()}{Component}Pipeline-{env}`
- Example: `colabsDBSPipeline-dev`, `colabsAdminWebPipeline-dev`

### Build Project Naming
- Pattern: `{projectName.lower()}{Component}Build-{env}`
- Example: `colabsDBSBuild-dev`, `colabsAdminWebBuild-dev`

## Architecture Patterns

### Stack Organization
- Each major component has its own stack file
- Stacks are instantiated in `app.py`
- Environment-specific configurations centralized in `environment.py`

### Pipeline Structure
- Source stage: BitBucket via CodeStar connections
- Build stage: CodeBuild with role assumption for cross-account deployment
- Each pipeline handles its own component's build and deployment

### Environment Management
- Multi-environment support (dev, staging, prod)
- Environment-specific ARNs, URLs, and IDs in `environment.py`
- Cross-account deployment using assumed roles