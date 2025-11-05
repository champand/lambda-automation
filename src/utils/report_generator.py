"""
Report Generator Module
======================

Generates comprehensive Excel reports of tagging operations.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)


def initialize_report() -> Dict[str, Any]:
    """
    Initialize report data structure.

    Returns:
        Dictionary containing report metadata and rows
    """
    return {
        'metadata': {
            'start_time': datetime.now(timezone.utc).isoformat(),
            'version': '1.0.0'
        },
        'rows': []
    }


def add_report_row(
    report_data: Dict[str, Any],
    sheet_name: str,
    row_number: int,
    row_data: Dict[str, Any],
    status: str,
    error_message: Optional[str],
    tags_applied: List[str]
) -> None:
    """
    Add a row to the report.

    Args:
        report_data: Report data structure
        sheet_name: Name of the sheet
        row_number: Original row number in input Excel
        row_data: Original row data
        status: Tagging status (SUCCESS, FAILED, PARTIAL, SKIPPED)
        error_message: Error message if failed
        tags_applied: List of tag keys successfully applied
    """
    report_row = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'sheet_name': sheet_name,
        'row_number': row_number,
        'account_id': row_data.get('accountId', 'N/A'),
        'resource_type': row_data.get('resourceType', sheet_name),
        'resource_id': row_data.get('resourceId', 'N/A'),
        'arn': row_data.get('arn', 'N/A'),
        'region': row_data.get('awsRegion', 'N/A'),
        'status': status,
        'tags_applied': ', '.join(tags_applied) if tags_applied else 'None',
        'tags_count': len(tags_applied),
        'error_message': error_message or ''
    }

    report_data['rows'].append(report_row)


def finalize_report(report_data: Dict[str, Any]) -> bytes:
    """
    Generate final Excel report.

    Args:
        report_data: Report data structure

    Returns:
        Excel file content as bytes
    """
    logger.info("Generating final Excel report")

    # Create workbook
    wb = Workbook()

    # Remove default sheet
    wb.remove(wb.active)

    # Create Summary sheet
    _create_summary_sheet(wb, report_data)

    # Create Details sheet
    _create_details_sheet(wb, report_data)

    # Save to BytesIO
    excel_buffer = BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)

    logger.info("Excel report generated successfully")

    return excel_buffer.getvalue()


def _create_summary_sheet(wb: Workbook, report_data: Dict[str, Any]) -> None:
    """Create summary sheet with statistics"""

    ws = wb.create_sheet("Summary")

    # Title
    ws['A1'] = "AWS Resource Tagging Report - Summary"
    ws['A1'].font = Font(size=16, bold=True)

    # Metadata
    row = 3
    ws[f'A{row}'] = "Generated At:"
    ws[f'B{row}'] = report_data['metadata']['start_time']
    row += 1

    ws[f'A{row}'] = "Report Version:"
    ws[f'B{row}'] = report_data['metadata']['version']
    row += 2

    # Statistics
    ws[f'A{row}'] = "Statistics"
    ws[f'A{row}'].font = Font(size=14, bold=True)
    row += 1

    rows = report_data['rows']
    total = len(rows)
    success = len([r for r in rows if r['status'] == 'SUCCESS'])
    failed = len([r for r in rows if r['status'] == 'FAILED'])
    partial = len([r for r in rows if r['status'] == 'PARTIAL'])
    skipped = len([r for r in rows if r['status'] == 'SKIPPED'])

    stats = [
        ("Total Resources Processed", total),
        ("Successful", success),
        ("Failed", failed),
        ("Partial", partial),
        ("Skipped", skipped),
        ("Success Rate", f"{(success / total * 100) if total > 0 else 0:.2f}%")
    ]

    for stat_name, stat_value in stats:
        ws[f'A{row}'] = stat_name
        ws[f'B{row}'] = stat_value
        ws[f'A{row}'].font = Font(bold=True)
        row += 1

    # Status breakdown by resource type
    row += 1
    ws[f'A{row}'] = "Breakdown by Resource Type"
    ws[f'A{row}'].font = Font(size=14, bold=True)
    row += 1

    # Group by resource type
    by_type = {}
    for r in rows:
        rtype = r['resource_type']
        if rtype not in by_type:
            by_type[rtype] = {'total': 0, 'success': 0, 'failed': 0}

        by_type[rtype]['total'] += 1
        if r['status'] == 'SUCCESS':
            by_type[rtype]['success'] += 1
        elif r['status'] == 'FAILED':
            by_type[rtype]['failed'] += 1

    # Headers
    ws[f'A{row}'] = "Resource Type"
    ws[f'B{row}'] = "Total"
    ws[f'C{row}'] = "Success"
    ws[f'D{row}'] = "Failed"
    for col in ['A', 'B', 'C', 'D']:
        ws[f'{col}{row}'].font = Font(bold=True)
        ws[f'{col}{row}'].fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
    row += 1

    # Data
    for rtype, stats in sorted(by_type.items()):
        ws[f'A{row}'] = rtype
        ws[f'B{row}'] = stats['total']
        ws[f'C{row}'] = stats['success']
        ws[f'D{row}'] = stats['failed']
        row += 1

    # Auto-size columns
    for col in ['A', 'B', 'C', 'D']:
        ws.column_dimensions[col].width = 25


def _create_details_sheet(wb: Workbook, report_data: Dict[str, Any]) -> None:
    """Create details sheet with all rows"""

    ws = wb.create_sheet("Details")

    # Headers
    headers = [
        "Timestamp",
        "Sheet Name",
        "Row Number",
        "Account ID",
        "Resource Type",
        "Resource ID",
        "ARN",
        "Region",
        "Status",
        "Tags Applied",
        "Tags Count",
        "Error Message"
    ]

    # Write headers
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Write data rows
    for row_idx, row_data in enumerate(report_data['rows'], start=2):
        ws.cell(row=row_idx, column=1, value=row_data['timestamp'])
        ws.cell(row=row_idx, column=2, value=row_data['sheet_name'])
        ws.cell(row=row_idx, column=3, value=row_data['row_number'])
        ws.cell(row=row_idx, column=4, value=row_data['account_id'])
        ws.cell(row=row_idx, column=5, value=row_data['resource_type'])
        ws.cell(row=row_idx, column=6, value=row_data['resource_id'])
        ws.cell(row=row_idx, column=7, value=row_data['arn'])
        ws.cell(row=row_idx, column=8, value=row_data['region'])

        # Status with color coding
        status_cell = ws.cell(row=row_idx, column=9, value=row_data['status'])
        if row_data['status'] == 'SUCCESS':
            status_cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
        elif row_data['status'] == 'FAILED':
            status_cell.fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")
        elif row_data['status'] == 'PARTIAL':
            status_cell.fill = PatternFill(start_color="FFD700", end_color="FFD700", fill_type="solid")
        else:  # SKIPPED
            status_cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

        ws.cell(row=row_idx, column=10, value=row_data['tags_applied'])
        ws.cell(row=row_idx, column=11, value=row_data['tags_count'])
        ws.cell(row=row_idx, column=12, value=row_data['error_message'])

    # Auto-size columns
    for col_idx in range(1, len(headers) + 1):
        col_letter = get_column_letter(col_idx)

        # Set width based on header
        if col_idx in [7, 12]:  # ARN and Error Message - wider
            ws.column_dimensions[col_letter].width = 60
        elif col_idx == 10:  # Tags Applied - medium
            ws.column_dimensions[col_letter].width = 40
        else:
            ws.column_dimensions[col_letter].width = 20

    # Freeze top row
    ws.freeze_panes = 'A2'

    # Add filters
    ws.auto_filter.ref = ws.dimensions


def generate_summary_stats(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate summary statistics from report data.

    Args:
        report_data: Report data structure

    Returns:
        Dictionary with summary statistics
    """
    rows = report_data['rows']
    total = len(rows)

    if total == 0:
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'partial': 0,
            'skipped': 0,
            'success_rate': 0.0
        }

    success = len([r for r in rows if r['status'] == 'SUCCESS'])
    failed = len([r for r in rows if r['status'] == 'FAILED'])
    partial = len([r for r in rows if r['status'] == 'PARTIAL'])
    skipped = len([r for r in rows if r['status'] == 'SKIPPED'])

    return {
        'total': total,
        'success': success,
        'failed': failed,
        'partial': partial,
        'skipped': skipped,
        'success_rate': round((success / total * 100), 2) if total > 0 else 0.0
    }
