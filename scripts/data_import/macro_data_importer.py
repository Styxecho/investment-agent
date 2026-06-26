#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Macro Data Importer
Import macro data from CSV/Excel, validate, and store to DB.
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, r'D:\Study\Project\investment-agent')

from data_external.db.engine import engine
from sqlalchemy import text

sys.path.insert(0, r'D:\Study\Project\investment-agent\scripts')
from data_import.parsers import auto_detect_parser
from data_import.config import VALIDATION_RULES

DOWNLOAD_DIR = Path(r'D:\Study\Project\investment-agent\data_external\downloads')
REPORT_DIR = Path(r'D:\Study\Project\investment-agent\docs\research\macro_analysis\reports')


class MacroDataImporter:
    def __init__(self):
        self.records = []
        self.errors = []
        self.warnings = []
        self.imported_count = 0
        self.updated_count = 0
        
    def scan_downloads(self):
        files = []
        if not DOWNLOAD_DIR.exists():
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            return files
        for ext in ['*.xlsx', '*.xls', '*.csv']:
            files.extend(DOWNLOAD_DIR.glob(ext))
        files = sorted(set(files), key=lambda x: x.stat().st_mtime, reverse=True)
        return files
    
    def parse_file(self, file_path):
        print("\n[1/5] Parsing file: %s" % file_path.name)
        parser, errors = auto_detect_parser(str(file_path))
        if parser is None:
            return [], errors
        records, parse_errors = parser.parse(str(file_path))
        print("      OK: %d records parsed" % len(records))
        if parse_errors:
            print("      WARN: %d parse errors" % len(parse_errors))
            for err in parse_errors[:3]:
                print("        - %s" % err)
        return records, parse_errors
    
    def validate_records(self, records):
        print("\n[2/5] Validating records")
        valid_records = []
        errors = []
        warnings = []
        
        for idx, record in enumerate(records):
            code = record.get('indicator_code')
            date_str = record.get('publish_date')
            value = record.get('value')
            
            if not code or not date_str or value is None or value == '':
                errors.append("Record #%d: Missing required fields" % idx)
                continue
            
            if code not in VALIDATION_RULES:
                warnings.append("Record #%d: Unknown indicator code '%s', skipping" % (idx, code))
                continue
            
            if len(str(date_str)) != 8 or not str(date_str).isdigit():
                errors.append("Record #%d: Invalid date format '%s'" % (idx, date_str))
                continue
            
            try:
                value = float(value)
            except:
                errors.append("Record #%d: Invalid value '%s'" % (idx, value))
                continue
            
            rules = VALIDATION_RULES.get(code, {})
            min_val = rules.get('min')
            max_val = rules.get('max')
            
            if min_val is not None and value < min_val:
                warnings.append("%s@%s: Value %.2f below minimum %.2f" % (code, date_str, value, min_val))
            
            if max_val is not None and value > max_val:
                warnings.append("%s@%s: Value %.2f above maximum %.2f" % (code, date_str, value, max_val))
            
            record['value'] = value
            valid_records.append(record)
        
        print("      OK: %d/%d records passed validation" % (len(valid_records), len(records)))
        if errors:
            print("      ERR: %d errors" % len(errors))
        if warnings:
            print("      WARN: %d warnings" % len(warnings))
        
        return valid_records, errors, warnings
    
    def import_to_db(self, records):
        print("\n[3/5] Importing to database")
        imported = 0
        updated = 0
        
        try:
            with engine.connect() as conn:
                for record in records:
                    code = record['indicator_code']
                    date_str = record['publish_date']
                    value = record['value']
                    freq = record.get('frequency', 'monthly')
                    
                    check_sql = text("SELECT 1 FROM macro_indicator_value WHERE indicator_code = :code AND publish_date = :date")
                    exists = conn.execute(check_sql, {"code": code, "date": date_str}).fetchone()
                    
                    if exists:
                        update_sql = text("UPDATE macro_indicator_value SET value = :value, updated_at = CURRENT_TIMESTAMP WHERE indicator_code = :code AND publish_date = :date")
                        conn.execute(update_sql, {"code": code, "date": date_str, "value": value})
                        updated += 1
                    else:
                        insert_sql = text("INSERT INTO macro_indicator_value (indicator_code, publish_date, value, frequency, data_source, created_at, updated_at) VALUES (:code, :date, :value, :freq, 'manual_import', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
                        conn.execute(insert_sql, {"code": code, "date": date_str, "value": value, "freq": freq})
                        imported += 1
                
                conn.commit()
        except Exception as e:
            print("      ERR: Database import failed: %s" % str(e)[:150])
            return 0, 0
        
        print("      OK: Imported %d new, Updated %d existing" % (imported, updated))
        return imported, updated
    
    def trigger_recalculation(self):
        print("\n[4/5] Triggering recalculation")
        try:
            sys.path.insert(0, r'D:\Study\Project\investment-agent')
            from skills.macro_state.service import MacroStateService
            service = MacroStateService()
            result = service.recalculate()
            if result.get('success'):
                print("      OK: Recalculation complete")
                print("        - Factors: %s records" % result.get('factor_count', 0))
                print("        - States: %s records" % result.get('state_count', 0))
                return True
            else:
                print("      ERR: Recalculation failed: %s" % result.get('message', 'Unknown error'))
                return False
        except Exception as e:
            print("      ERR: Recalculation failed: %s" % str(e)[:150])
            return False
    
    def generate_report(self, records, imported, updated):
        print("\n[5/5] Generating report")
        report_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = REPORT_DIR / ("import_report_%s.md" % report_time)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        indicator_stats = {}
        for record in records:
            code = record['indicator_code']
            if code not in indicator_stats:
                indicator_stats[code] = {'count': 0, 'dates': []}
            indicator_stats[code]['count'] += 1
            indicator_stats[code]['dates'].append(record['publish_date'])
        
        report_content = "# Macro Data Import Report\n\n"
        report_content += "**Import Time**: %s\n\n" % datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report_content += "## Summary\n\n"
        report_content += "| Item | Value |\n"
        report_content += "|------|-------|\n"
        report_content += "| Records Parsed | %d |\n" % len(records)
        report_content += "| New Records | %d |\n" % imported
        report_content += "| Updated Records | %d |\n" % updated
        report_content += "| Indicators | %d |\n\n" % len(indicator_stats)
        
        report_content += "## Indicator Details\n\n"
        report_content += "| Indicator Code | Count | Date Range |\n"
        report_content += "|----------------|-------|------------|\n"
        for code, stats in sorted(indicator_stats.items()):
            dates = sorted(stats['dates'])
            date_range = "%s ~ %s" % (dates[0], dates[-1]) if len(dates) > 1 else dates[0]
            report_content += "| %s | %d | %s |\n" % (code, stats['count'], date_range)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print("      OK: Report saved to %s" % report_file)
        return str(report_file)
    
    def run(self, file_path=None, auto_scan=False):
        print("=" * 70)
        print("Macro Data Importer")
        print("=" * 70)
        print("Current Time: %s" % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print()
        
        if file_path:
            files = [Path(file_path)]
        elif auto_scan:
            files = self.scan_downloads()
            if not files:
                print("No files found in download directory")
                print("Place Excel files in: %s" % DOWNLOAD_DIR)
                return {"success": False, "message": "No files to import"}
            print("Found %d files to import" % len(files))
        else:
            return {"success": False, "message": "Specify --file or --auto"}
        
        all_records = []
        all_errors = []
        
        for file in files:
            records, errors = self.parse_file(file)
            all_records.extend(records)
            all_errors.extend(errors)
        
        if not all_records:
            print("\nNo valid records found")
            return {"success": False, "message": "Parsing failed", "errors": all_errors}
        
        valid_records, val_errors, val_warnings = self.validate_records(all_records)
        self.errors.extend(val_errors)
        self.warnings.extend(val_warnings)
        
        if not valid_records:
            print("\nValidation failed, no valid records to import")
            return {"success": False, "message": "Validation failed", "errors": self.errors}
        
        imported, updated = self.import_to_db(valid_records)
        self.imported_count = imported
        self.updated_count = updated
        
        if imported == 0 and updated == 0:
            print("\nDatabase import failed")
            return {"success": False, "message": "Import failed"}
        
        recalc_success = self.trigger_recalculation()
        report_path = self.generate_report(valid_records, imported, updated)
        
        print("\n" + "=" * 70)
        print("Import Complete!")
        print("=" * 70)
        print("New: %d | Updated: %d" % (imported, updated))
        print("Report: %s" % report_path)
        print("=" * 70)
        
        return {
            "success": True,
            "imported": imported,
            "updated": updated,
            "report": report_path,
            "recalc_success": recalc_success,
            "errors": self.errors,
            "warnings": self.warnings
        }


def generate_template(year, month):
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    publish_date = "%d%02d%02d" % (year, month, last_day)
    
    monthly_indicators = [
        ('CN_PMI_MFG_M', 'Manufacturing PMI', '%'),
        ('CN_PMI_SVC_M', 'Non-manufacturing PMI', '%'),
        ('CN_PMI_COMP_M', 'Composite PMI', '%'),
        ('CN_IAV_YOY_M', 'Industrial Production YoY', '%'),
        ('CN_CPI_YOY_M', 'CPI YoY', '%'),
        ('CN_CCPI_YOY_M', 'Core CPI YoY', '%'),
        ('CN_CPI_MOM_M', 'CPI MoM', '%'),
        ('CN_CCPI_MOM_M', 'Core CPI MoM', '%'),
        ('CN_PPI_YOY_M', 'PPI YoY', '%'),
        ('CN_PPI_MOM_M', 'PPI MoM', '%'),
        ('CN_M2_YOY_M', 'M2 YoY', '%'),
        ('CN_M1_YOY_M', 'M1 YoY', '%'),
        ('CN_M0_YOY_M', 'M0 YoY', '%'),
        ('CN_SFS_YOY_M', 'Social Financing Stock YoY', '%'),
        ('CN_SFS_FLOW_M', 'Social Financing Flow', '100M CNY'),
    ]
    
    rows = []
    for code, name, unit in monthly_indicators:
        rows.append({
            'indicator_code': code,
            'indicator_name': name,
            'publish_date': publish_date,
            'value': '',
            'unit': unit,
            'frequency': 'monthly',
            'source': 'Stats/PBC',
            'notes': ''
        })
    
    df = pd.DataFrame(rows)
    template_file = DOWNLOAD_DIR / "macro_monthly_template.csv"
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(template_file, index=False, encoding='utf-8-sig')
    
    print("\nTemplate generated: %s" % template_file)
    print("Indicators: %d" % len(df))
    print("\nInstructions:")
    print("1. Fill in the 'value' column with actual data")
    print("2. Save and run: python scripts/data_import/macro_data_importer.py --auto")
    
    return str(template_file)


def check_data_freshness():
    print("=" * 70)
    print("Macro Data Freshness Check")
    print("=" * 70)
    
    try:
        sql = """
        SELECT v.indicator_code, c.indicator_name, MAX(v.publish_date) as latest_date, COUNT(*) as record_count
        FROM macro_indicator_value v
        JOIN macro_indicator_catalog c ON v.indicator_code = c.indicator_code
        WHERE c.is_active = 1
        GROUP BY v.indicator_code
        ORDER BY c.category, v.indicator_code
        """
        df = pd.read_sql(sql, engine)
        
        print("\nCurrent Date: %s" % date.today().strftime('%Y-%m-%d'))
        print("\n%-20s %-12s %-10s" % ("Indicator", "Latest Date", "Status"))
        print("-" * 50)
        
        stale_count = 0
        for _, row in df.iterrows():
            code = row['indicator_code']
            latest = row['latest_date']
            
            should_have_april = code in [
                'CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M',
                'CN_CPI_YOY_M', 'CN_PPI_YOY_M',
                'CN_M2_YOY_M', 'CN_SFS_YOY_M', 'CN_IAV_YOY_M'
            ]
            
            if should_have_april and str(latest) < '20260430':
                status = "NEEDS APR"
                stale_count += 1
            elif str(latest) >= '20260430':
                status = "UPDATED"
            else:
                status = "OK"
            
            print("%-20s %-12s %-10s" % (code, latest, status))
        
        print("\nIndicators needing update: %d" % stale_count)
        
        if stale_count > 0:
            print("\nRecommended actions:")
            print("1. Generate template: python scripts/data_import/macro_data_importer.py --template")
            print("2. Fill data and run: python scripts/data_import/macro_data_importer.py --auto")
        
    except Exception as e:
        print("Check failed: %s" % str(e)[:150])


def main():
    parser = argparse.ArgumentParser(description='Macro Data Importer')
    parser.add_argument('--auto', action='store_true', help='Auto scan and import')
    parser.add_argument('--file', type=str, help='Specify file to import')
    parser.add_argument('--template', action='store_true', help='Generate data template')
    parser.add_argument('--year', type=int, default=datetime.now().year, help='Template year')
    parser.add_argument('--month', type=int, default=datetime.now().month, help='Template month')
    parser.add_argument('--check', action='store_true', help='Check data freshness')
    parser.add_argument('--no-recalc', action='store_true', help='Skip recalculation')
    
    args = parser.parse_args()
    
    if args.check:
        check_data_freshness()
        return
    
    if args.template:
        generate_template(args.year, args.month)
        return
    
    if args.auto or args.file:
        importer = MacroDataImporter()
        result = importer.run(file_path=args.file, auto_scan=args.auto)
        
        if result.get('success'):
            print("\nImport successful!")
        else:
            print("\nImport failed: %s" % result.get('message'))
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
