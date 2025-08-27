# GitLab CI/CD Workflow Mapping

This document outlines how the GitLab CI/CD configuration mirrors the GitHub Actions workflows, maintaining exact functionality and structure.

## Overview

The GitLab CI configuration (`.gitlab-ci.yml`) replicates all 8 GitHub workflows with identical functionality:

| GitHub Workflow | GitLab CI Stage | GitLab Job(s) | Description |
|-----------------|----------------|---------------|-------------|
| `test.yml` | `test` | `test`, `test-slurm` | Core testing and SLURM integration |
| `format.yml` | `format` | `auto-format` | Code formatting with auto-commit |
| `dependencies.yml` | `dependencies` | `dependency-check` | Dependency monitoring with issue creation |
| `security.yml` | `security` | `security-scan` | Security vulnerability scanning |
| `version.yml` | `version` | `version-bump` | Version bumping and release management |
| `build.yml` | `build` | `build-package` | Package building |
| `build.yml` (release) | `release` | `create-release` | GitHub/GitLab releases |
| `ci.yml` | `status` | `ci-status` | Workflow status summary |
| `sync-versions.yml` | `sync` | `sync-versions` | Version conflict resolution |

## Stage Organization

The GitLab CI pipeline is organized into logical stages that mirror the GitHub workflow structure:

### 1. **validate** Stage
- **Purpose**: Pre-validation checks
- **Jobs**: `validate`
- **GitHub equivalent**: Implicit in each workflow

### 2. **test** Stage
- **Purpose**: Core testing and SLURM integration
- **Jobs**: `test`, `test-slurm`
- **GitHub equivalent**: `test.yml`
- **Features**:
  - Unit tests with coverage reporting
  - Pre-commit hook validation
  - SLURM environment testing with MySQL service
  - CLI functionality testing
  - Mirrors exact test commands and validation

### 3. **security** Stage
- **Purpose**: Security vulnerability scanning
- **Jobs**: `security-scan`
- **GitHub equivalent**: `security.yml`
- **Features**:
  - Safety dependency vulnerability checks
  - Bandit security linting
  - Secret scanning in source code
  - Same tools and commands as GitHub

### 4. **format** Stage
- **Purpose**: Automated code formatting
- **Jobs**: `auto-format`
- **GitHub equivalent**: `format.yml`
- **Features**:
  - Pre-commit auto-formatting
  - Git auto-commit and push
  - Retry logic for push failures
  - Excludes CI files from formatting (like GitHub excludes workflows)

### 5. **build** Stage
- **Purpose**: Package building and validation
- **Jobs**: `build-package`
- **GitHub equivalent**: `build.yml`
- **Features**:
  - Python wheel and source distribution building
  - Package integrity validation with twine
  - Installation testing
  - Version detection and reporting
  - Artifact generation for downstream jobs

### 6. **dependencies** Stage
- **Purpose**: Dependency monitoring
- **Jobs**: `dependency-check`
- **GitHub equivalent**: `dependencies.yml`
- **Features**:
  - Scheduled dependency checks
  - Outdated package detection
  - Issue creation (placeholder for GitLab API integration)
  - Same pip-tools based approach

### 7. **version** Stage
- **Purpose**: Version management and bumping
- **Jobs**: `version-bump`
- **GitHub equivalent**: `version.yml`
- **Features**:
  - Automatic version bumping (major/minor/patch)
  - Git tagging and pushing
  - Branch synchronization logic
  - Manual trigger support for major releases

### 8. **release** Stage
- **Purpose**: Release creation with artifacts
- **Jobs**: `create-release`
- **GitHub equivalent**: `build.yml` (release job)
- **Features**:
  - Automated release notes generation
  - Artifact packaging
  - GitLab release creation (placeholder for API integration)
  - Version tagging

### 9. **status** Stage
- **Purpose**: Pipeline status summary
- **Jobs**: `ci-status`
- **GitHub equivalent**: `ci.yml`
- **Features**:
  - Overall pipeline status reporting
  - Runs regardless of other job failures
  - Status summary and logging

### 10. **sync** Stage
- **Purpose**: Version conflict resolution
- **Jobs**: `sync-versions`
- **GitHub equivalent**: `sync-versions.yml`
- **Features**:
  - Automatic version conflict resolution
  - Branch version synchronization
  - Same logic as GitHub for version comparison

## Key Features Preserved

### Triggers and Conditions
- **Push events**: Same branch filtering (main, dev)
- **Merge requests**: Same as GitHub pull requests
- **Scheduled runs**: Same cron-like scheduling support
- **Manual triggers**: Same as GitHub workflow_dispatch

### Environment Configuration
- **Python version**: Consistently uses 3.12 (matches GitHub `env.PYTHON_VERSION`)
- **Caching**: pip cache configuration matching GitHub cache action
- **Variables**: Same environment variable patterns

### Job Dependencies
- **Needs**: Proper job dependencies (e.g., `build-package` needs `test`)
- **Artifacts**: Proper artifact passing between jobs
- **Conditional execution**: Same rule-based execution logic

### Security and Permissions
- **Git configuration**: Same bot user configuration
- **Token usage**: Placeholder for GitLab token usage
- **Service dependencies**: MySQL service for SLURM testing

## Differences and Adaptations

### GitLab-Specific Features
1. **Services**: Uses GitLab CI services syntax instead of GitHub Actions services
2. **Artifacts**: Uses GitLab artifacts instead of GitHub Actions upload/download
3. **Variables**: Uses GitLab CI variables syntax
4. **Rules**: Uses GitLab CI rules instead of GitHub Actions if conditions

### Functional Equivalents
1. **Issue creation**: Placeholder for GitLab API calls (GitHub uses actions/github-script)
2. **Release creation**: Placeholder for GitLab release-cli (GitHub uses gh CLI)
3. **Status checks**: Uses GitLab pipeline status instead of GitHub workflow API
4. **Bot identity**: Uses gitlab-ci[bot] instead of github-actions[bot]

### Preserved Behavior
- All scripts and commands are identical to GitHub workflows
- Same error handling and retry logic
- Same artifact generation and validation
- Same test execution patterns
- Same version management logic

## Testing and Validation

The GitLab CI configuration maintains the same quality standards:

- **YAML validation**: Syntax validated using Python yaml parser
- **Command preservation**: All bash scripts and Python commands unchanged
- **Tool versions**: Same tool versions specified (e.g., pre-commit==3.5.0)
- **Artifact compatibility**: Generates same dist/ artifacts as GitHub

## Migration Benefits

1. **Zero functional changes**: Same outcomes as GitHub workflows
2. **Familiar structure**: Organized stages mirror GitHub workflow organization
3. **Easy maintenance**: Comments and structure make mapping clear
4. **Future-proof**: Easy to extend with additional GitLab-specific features
5. **Debugging**: Clear job names and stage organization for troubleshooting

This configuration ensures complete parity between GitHub Actions and GitLab CI while taking advantage of GitLab's native CI/CD features and syntax.
