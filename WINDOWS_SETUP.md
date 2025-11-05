# Windows Setup Guide

Step-by-step guide for Windows users to set up and run the AWS Lambda Tagging Automation project.

## Issue: "Python was not found"

If you see this error when running Python scripts:
```
Python was not found; run without arguments to install from the Microsoft Store...
```

This means Python is not installed or not in your system PATH.

## Solution 1: Install Python (Recommended)

### Step 1: Download Python

1. Go to: https://www.python.org/downloads/
2. Click "Download Python 3.12.x" (latest version)
3. **IMPORTANT**: Check the box "Add Python to PATH" during installation
4. Click "Install Now"

### Step 2: Verify Installation

Open a new Command Prompt (or PowerShell) and run:

```cmd
python --version
```

You should see: `Python 3.12.x`

### Step 3: Install Dependencies

```cmd
cd lambda-automation
pip install -r requirements.txt
```

### Step 4: Generate Sample File

```cmd
cd examples
python create_sample_input.py
```

---

## Solution 2: Use Pre-Generated Sample File

**Good news!** A pre-generated sample Excel file is already available:

📁 **Location:** `sample_tagging_input.xlsx` (in project root)

You can:
1. Open it directly in Excel
2. Use it as a template for your input files
3. Upload it to S3 for testing

### Sample File Contents:

- **6 sheets**: EC2, EBS, S3, RDS, EKS, LB
- **8 example resources** with cost allocation tags
- **Formatted headers** with proper column names

---

## Solution 3: Use Python from Microsoft Store

1. Open Microsoft Store
2. Search for "Python 3.12"
3. Click "Get" to install
4. Open a new Command Prompt
5. Run: `python --version`

---

## Alternative: Use WSL (Windows Subsystem for Linux)

If you prefer using Linux commands on Windows:

### Install WSL:

```powershell
wsl --install
```

### After WSL is installed:

```bash
# Open WSL terminal
wsl

# Navigate to project
cd /mnt/c/path/to/lambda-automation

# Install dependencies
pip3 install -r requirements.txt

# Generate sample
cd examples
python3 create_sample_input.py
```

---

## Troubleshooting

### Python Command Not Found After Installation

**Cause**: Python not in PATH

**Solution**:
1. Search for "Environment Variables" in Windows Start Menu
2. Click "Edit the system environment variables"
3. Click "Environment Variables" button
4. Under "User variables", find "Path"
5. Click "Edit"
6. Click "New" and add:
   - `C:\Users\<YourUsername>\AppData\Local\Programs\Python\Python312`
   - `C:\Users\<YourUsername>\AppData\Local\Programs\Python\Python312\Scripts`
7. Click "OK" on all dialogs
8. **Close and reopen** Command Prompt

### pip is not recognized

**Solution**:
```cmd
python -m pip install --upgrade pip
```

### ModuleNotFoundError: No module named 'openpyxl'

**Solution**:
```cmd
pip install openpyxl
```

---

## Using PowerShell Instead of Command Prompt

PowerShell commands are slightly different:

```powershell
# Check Python version
python --version

# Install dependencies
pip install -r requirements.txt

# Generate sample
cd examples
python create_sample_input.py

# List files
Get-ChildItem

# View file contents
Get-Content README.md
```

---

## Running Tests on Windows

```cmd
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## AWS CLI Setup on Windows

### Install AWS CLI v2:

1. Download: https://awscli.amazonaws.com/AWSCLIV2.msi
2. Run the installer
3. Verify: `aws --version`

### Configure AWS Credentials:

```cmd
aws configure
```

Enter:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `ap-south-1`)
- Default output format (e.g., `json`)

---

## Building Lambda Package on Windows

### Option 1: Use PowerShell (requires modification)

The provided `package_lambda.sh` is a bash script. For Windows, create `package_lambda.ps1`:

```powershell
# PowerShell equivalent (simplified)
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path build/package

pip install -r requirements.txt --target build/package

Copy-Item -Recurse src/lambda_function build/package/
Copy-Item -Recurse src/utils build/package/

Compress-Archive -Path build/package/* -DestinationPath lambda-deployment-package.zip -Force

Write-Host "✓ Package created: lambda-deployment-package.zip"
```

### Option 2: Use Docker (Recommended for Windows)

```cmd
docker run --rm -v %cd%:/var/task public.ecr.aws/lambda/python:3.12 /bin/bash -c "pip install -r requirements.txt -t package && cd package && zip -r ../lambda-deployment-package.zip . && cd .. && zip -r lambda-deployment-package.zip src/"
```

### Option 3: Use WSL

```bash
wsl
cd /mnt/c/path/to/lambda-automation
./scripts/package_lambda.sh
```

---

## Deploying from Windows

All AWS CLI commands work the same on Windows:

```cmd
aws cloudformation deploy ^
  --template-file cloudformation/management-account-roles.yaml ^
  --stack-name lambda-tagging-automation ^
  --capabilities CAPABILITY_NAMED_IAM

aws lambda update-function-code ^
  --function-name ResourceTaggingAutomation ^
  --zip-file fileb://lambda-deployment-package.zip
```

**Note**: Use `^` for line continuation in Command Prompt, or `` ` `` in PowerShell.

---

## Recommended Tools for Windows Development

1. **VS Code** - https://code.visualstudio.com/
   - Install Python extension
   - Integrated terminal

2. **Git for Windows** - https://git-scm.com/download/win
   - Includes Git Bash (Unix-like terminal)

3. **Windows Terminal** - https://aka.ms/terminal
   - Modern terminal with tabs
   - Better PowerShell experience

---

## Quick Reference: Command Prompt vs PowerShell vs WSL

| Task | Command Prompt | PowerShell | WSL |
|------|---------------|------------|-----|
| List files | `dir` | `Get-ChildItem` or `ls` | `ls` |
| Change directory | `cd path` | `cd path` | `cd path` |
| Create directory | `mkdir name` | `New-Item -ItemType Directory name` | `mkdir name` |
| Delete file | `del file` | `Remove-Item file` | `rm file` |
| View file | `type file` | `Get-Content file` | `cat file` |
| Run Python | `python script.py` | `python script.py` | `python3 script.py` |

---

## Need Help?

- Check the main **README.md** for full documentation
- See **DEPLOYMENT_GUIDE.md** for deployment steps
- Review **PROJECT_STRUCTURE.md** for code organization

---

## Pre-Generated Files Included

You don't need to run any Python scripts if you use these pre-generated files:

✅ `sample_tagging_input.xlsx` - Ready to use sample input
✅ CloudFormation templates - Ready to deploy
✅ All Python source code - Ready to package

---

**For most users**: You can skip the sample generation step and use the included `sample_tagging_input.xlsx` file directly!
