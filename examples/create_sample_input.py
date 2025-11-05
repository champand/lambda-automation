#!/usr/bin/env python3
"""
Create Sample Input Excel File
===============================

This script generates a sample Excel input file for the AWS Lambda
tagging automation with multiple sheets and example data.

Usage:
    python create_sample_input.py
"""

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

def create_sample_input():
    """Create sample input Excel file with multiple sheets."""

    wb = Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # Define sample data for different resource types
    sheets_data = {
        'EC2': [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0',
                'accountId': '123456789012',
                'resourceType': 'EC2',
                'resourceId': 'i-1234567890abcdef0',
                'awsRegion': 'us-east-1',
                'pl:cost-allocation:environment': 'production',
                'pl:cost-allocation:team': 'platform',
                'pl:cost-allocation:project': 'web-app',
                'pl:cost-allocation:cost-center': 'engineering'
            },
            {
                'accountId': '123456789012',
                'resourceType': 'EC2',
                'resourceId': 'i-abcdef1234567890',
                'awsRegion': 'us-west-2',
                'pl:cost-allocation:environment': 'development',
                'pl:cost-allocation:team': 'backend',
                'pl:cost-allocation:project': 'api-service',
                'pl:cost-allocation:cost-center': 'engineering'
            }
        ],
        'EBS': [
            {
                'arn': 'arn:aws:ec2:us-east-1:123456789012:volume/vol-1234567890abcdef0',
                'accountId': '123456789012',
                'resourceType': 'EBS',
                'resourceId': 'vol-1234567890abcdef0',
                'awsRegion': 'us-east-1',
                'pl:cost-allocation:environment': 'production',
                'pl:cost-allocation:team': 'platform',
                'pl:cost-allocation:project': 'database'
            }
        ],
        'S3': [
            {
                'arn': 'arn:aws:s3:::my-production-bucket',
                'accountId': '123456789012',
                'resourceType': 'S3',
                'resourceId': 'my-production-bucket',
                'awsRegion': 'us-east-1',
                'pl:cost-allocation:environment': 'production',
                'pl:cost-allocation:team': 'data',
                'pl:cost-allocation:project': 'analytics',
                'pl:cost-allocation:data-classification': 'confidential'
            },
            {
                'accountId': '987654321098',
                'resourceType': 'S3',
                'resourceId': 'my-dev-bucket',
                'awsRegion': 'us-west-2',
                'pl:cost-allocation:environment': 'development',
                'pl:cost-allocation:team': 'data',
                'pl:cost-allocation:project': 'analytics'
            }
        ],
        'RDS': [
            {
                'arn': 'arn:aws:rds:us-east-1:123456789012:db:production-db',
                'accountId': '123456789012',
                'resourceType': 'RDS',
                'resourceId': 'production-db',
                'awsRegion': 'us-east-1',
                'pl:cost-allocation:environment': 'production',
                'pl:cost-allocation:team': 'backend',
                'pl:cost-allocation:project': 'web-app',
                'pl:cost-allocation:criticality': 'high'
            }
        ],
        'EKS': [
            {
                'arn': 'arn:aws:eks:us-east-1:123456789012:cluster/production-cluster',
                'accountId': '123456789012',
                'resourceType': 'EKS',
                'resourceId': 'production-cluster',
                'awsRegion': 'us-east-1',
                'pl:cost-allocation:environment': 'production',
                'pl:cost-allocation:team': 'platform',
                'pl:cost-allocation:project': 'kubernetes-infra'
            }
        ],
        'LB': [
            {
                'arn': 'arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/prod-alb/1234567890abcdef',
                'accountId': '123456789012',
                'resourceType': 'LB',
                'awsRegion': 'us-east-1',
                'pl:cost-allocation:environment': 'production',
                'pl:cost-allocation:team': 'platform',
                'pl:cost-allocation:project': 'web-app'
            }
        ]
    }

    # Create sheets
    for sheet_name, rows in sheets_data.items():
        ws = wb.create_sheet(sheet_name)

        # Get headers from first row
        if rows:
            headers = list(rows[0].keys())

            # Write headers with formatting
            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                cell.alignment = Alignment(horizontal='center', vertical='center')

            # Write data rows
            for row_idx, row_data in enumerate(rows, start=2):
                for col_idx, header in enumerate(headers, start=1):
                    value = row_data.get(header, '')
                    ws.cell(row=row_idx, column=col_idx, value=value)

            # Auto-size columns
            for col_idx, header in enumerate(headers, start=1):
                col_letter = ws.cell(row=1, column=col_idx).column_letter
                if header == 'arn':
                    ws.column_dimensions[col_letter].width = 80
                elif header.startswith('pl:cost-allocation:'):
                    ws.column_dimensions[col_letter].width = 30
                else:
                    ws.column_dimensions[col_letter].width = 20

    # Save workbook
    output_file = 'sample_tagging_input.xlsx'
    wb.save(output_file)
    print(f"✅ Sample input file created: {output_file}")
    print(f"   Sheets created: {', '.join(sheets_data.keys())}")
    print(f"   Total rows: {sum(len(rows) for rows in sheets_data.values())}")


if __name__ == '__main__':
    create_sample_input()
