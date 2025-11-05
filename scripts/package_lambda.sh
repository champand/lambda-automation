#!/bin/bash
##############################################################################
# AWS Lambda Deployment Package Builder
##############################################################################
#
# This script creates a deployment package (.zip) for the AWS Lambda function
# including all Python code and dependencies.
#
# Usage:
#   ./scripts/package_lambda.sh
#
# Output:
#   lambda-deployment-package.zip
#
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"
PACKAGE_DIR="${BUILD_DIR}/package"
OUTPUT_ZIP="${PROJECT_ROOT}/lambda-deployment-package.zip"
SRC_DIR="${PROJECT_ROOT}/src"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AWS Lambda Deployment Package Builder                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# Step 1: Clean previous builds
echo -e "${YELLOW}[Step 1/6]${NC} Cleaning previous builds..."
rm -rf "${BUILD_DIR}"
rm -f "${OUTPUT_ZIP}"
mkdir -p "${PACKAGE_DIR}"
echo -e "${GREEN}✓${NC} Build directory cleaned"
echo

# Step 2: Check Python version
echo -e "${YELLOW}[Step 2/6]${NC} Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: ${PYTHON_VERSION}"

if ! python3 -c 'import sys; assert sys.version_info >= (3, 12)' 2>/dev/null; then
    echo -e "${RED}✗${NC} Python 3.12+ required. Found: ${PYTHON_VERSION}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python version compatible"
echo

# Step 3: Install dependencies
echo -e "${YELLOW}[Step 3/6]${NC} Installing Python dependencies..."
pip3 install -q --target "${PACKAGE_DIR}" -r "${PROJECT_ROOT}/requirements.txt"

# Remove unnecessary files to reduce package size
echo "Removing unnecessary files..."
find "${PACKAGE_DIR}" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "${PACKAGE_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${PACKAGE_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
find "${PACKAGE_DIR}" -type f -name "*.pyo" -delete 2>/dev/null || true
find "${PACKAGE_DIR}" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "${PACKAGE_DIR}" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

echo -e "${GREEN}✓${NC} Dependencies installed"
echo

# Step 4: Copy Lambda function code
echo -e "${YELLOW}[Step 4/6]${NC} Copying Lambda function code..."

# Copy the lambda_function directory
cp -r "${SRC_DIR}/lambda_function" "${PACKAGE_DIR}/"

# Copy the utils directory
cp -r "${SRC_DIR}/utils" "${PACKAGE_DIR}/"

echo -e "${GREEN}✓${NC} Lambda code copied"
echo

# Step 5: Create deployment package
echo -e "${YELLOW}[Step 5/6]${NC} Creating deployment package..."
cd "${PACKAGE_DIR}"
zip -q -r "${OUTPUT_ZIP}" .
cd "${PROJECT_ROOT}"

# Get package size
PACKAGE_SIZE=$(du -h "${OUTPUT_ZIP}" | cut -f1)

echo -e "${GREEN}✓${NC} Deployment package created"
echo

# Step 6: Validate package
echo -e "${YELLOW}[Step 6/6]${NC} Validating package..."

# Check if lambda_handler exists in package
if unzip -l "${OUTPUT_ZIP}" | grep -q "lambda_function/tag_resources_lambda.py"; then
    echo -e "${GREEN}✓${NC} Lambda handler found"
else
    echo -e "${RED}✗${NC} Lambda handler not found in package"
    exit 1
fi

# Check if dependencies exist
if unzip -l "${OUTPUT_ZIP}" | grep -q "boto3"; then
    echo -e "${GREEN}✓${NC} boto3 dependency found"
else
    echo -e "${RED}✗${NC} boto3 dependency not found in package"
    exit 1
fi

if unzip -l "${OUTPUT_ZIP}" | grep -q "openpyxl"; then
    echo -e "${GREEN}✓${NC} openpyxl dependency found"
else
    echo -e "${RED}✗${NC} openpyxl dependency not found in package"
    exit 1
fi

echo

# Final summary
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Build Complete!                                         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo
echo -e "${GREEN}Package Location:${NC} ${OUTPUT_ZIP}"
echo -e "${GREEN}Package Size:${NC}     ${PACKAGE_SIZE}"
echo
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Deploy to AWS Lambda:"
echo "   aws lambda update-function-code \\"
echo "     --function-name ResourceTaggingAutomation \\"
echo "     --zip-file fileb://${OUTPUT_ZIP}"
echo
echo "2. Or upload via AWS Console:"
echo "   Lambda → Functions → ResourceTaggingAutomation → Upload from → .zip file"
echo
echo -e "${GREEN}✓${NC} All done!"
