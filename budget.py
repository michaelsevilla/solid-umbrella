import sys
import csv
import json
import os
import http.server
from datetime import datetime

def get_short_income_desc(desc):
    """Create a shorter, more readable description for an income source."""
    desc_lower = desc.lower()
    # Keywords that often separate the company name from transaction details
    separators = ['payroll', 'ppd id', 'direct dep', 'payment']
    for sep in separators:
        idx = desc_lower.find(sep)
        # Ensure separator is found and is not at the very beginning of the string.
        if idx > 0:
            # Take the substring before the separator and clean it up.
            short_desc = desc[:idx].strip().rstrip('-_ ')
            if short_desc:
                return short_desc
    return desc

def generate_html(all_data, overrides):
    data_json = json.dumps(all_data)
    overrides_json = json.dumps(overrides)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, 'template.html')
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html_template = f.read()
    except FileNotFoundError:
        print(f"\n❌ ERROR: Could not find '{template_path}'")
        print("Please ensure you created the 'template.html' file from the previous step in the same folder as budget.py!")
        sys.exit(1)

    html_template = html_template.replace('__DATA_JSON__', data_json)
    html_template = html_template.replace('__OVERRIDES_JSON__', overrides_json)
    
    with open('report.html', 'w', encoding='utf-8') as f:
        f.write(html_template)
    print(f"Report generated: {os.path.abspath('report.html')}")

class BudgetHandler(http.server.SimpleHTTPRequestHandler):
    csv_files = [] # Class attribute to hold csv file paths

    def do_GET(self):
        if self.path == '/data':
            try:
                all_data, overrides = process_files(self.csv_files)
                response_data = json.dumps({'data': all_data, 'overrides': overrides})
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(response_data.encode('utf-8'))
            except Exception as e:
                self.send_error(500, f"Error processing data: {e}")
            return
        
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if self.path == '/save_overrides':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            overrides_file = os.path.join(script_dir, 'overrides.json')
            
            with open(overrides_file, 'wb') as f:
                f.write(post_data)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def process_files(csv_files):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    overrides_file = os.path.join(script_dir, 'overrides.json')
    if not os.path.exists(overrides_file):
        overrides_file = 'overrides.json'  # Fallback to current working directory

    overrides = {'description_mapping': {}, 'exact_mapping': {}, 'ignored_descriptions': [], 'ignored_exact': [], 'moved_transactions': {}, 'expected_rename_mapping': {}}
    if os.path.exists(overrides_file):
        try:
            with open(overrides_file, 'r') as f:
                loaded_overrides = json.load(f)
                overrides.update(loaded_overrides)
                if 'expected_rename_mapping' not in overrides: overrides['expected_rename_mapping'] = {}
                if 'moved_transactions' not in overrides: overrides['moved_transactions'] = {}
                if 'ignored_descriptions' not in overrides: overrides['ignored_descriptions'] = []
                if 'ignored_exact' not in overrides: overrides['ignored_exact'] = []
        except Exception as e:
            print(f"Could not load {overrides_file}: {e}")

    monthly_data = {}

    for csv_filename in csv_files:
        try:
            with open(csv_filename, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row = {str(k).strip(): str(v) if v is not None else '' for k, v in row.items() if k is not None}
                    
                    # Improved Date Parsing: Look for common date keys
                    date_val = 'N/A'
                    for key in row.keys():
                        if 'date' in key.lower():
                            date_val = row[key]
                            break
                    
                    # Parse month (supports MM/DD/YYYY and YYYY-MM-DD formats)
                    month_key = 'Unknown'
                    if date_val != 'N/A':
                        try:
                            dt = datetime.strptime(date_val, '%m/%d/%Y')
                            month_key = dt.strftime('%Y-%m')
                        except ValueError:
                            try:
                                dt = datetime.strptime(date_val, '%Y-%m-%d')
                                month_key = dt.strftime('%Y-%m')
                            except ValueError:
                                # Fallback if unrecognized date format
                                month_key = date_val[:7] if len(date_val) >= 7 else date_val
                    
                    desc = 'N/A'
                    for key in row.keys():
                        k_lower = key.lower()
                        if 'date' in k_lower:
                            continue
                        if any(x in k_lower for x in ['description', 'desc', 'name', 'memo', 'payee', 'transaction']):
                            desc = row[key]
                            break
                    
                    # Normalize whitespace (HTML collapses spaces, so we should too for accurate substring matching)
                    desc = " ".join(desc.split())
                    
                    # Skip credit card payoffs
                    if 'payment thank you' in desc.lower():
                        continue
                    
                    amt_str = '0'
                    for key in row.keys():
                        if 'amount' in key.lower():
                            amt_str = row[key]
                            break
                    
                    # Checking accounts often use Debit / Credit columns instead of a single Amount column
                    if amt_str == '0':
                        for key in row.keys():
                            if 'debit' in key.lower() and row[key].strip():
                                amt_str = '-' + row[key].strip().replace('-', '')
                                break
                            elif 'credit' in key.lower() and row[key].strip():
                                amt_str = row[key].strip()
                                break

                    amt_str = amt_str.replace('$', '').replace(',', '')
                    try:
                        amt = float(amt_str)
                    except ValueError:
                        amt = 0.0

                    is_income = False
                    desc_lower = desc.lower()
                    # Detect income from specific payroll strings
                    if amt > 0 and any(kw in desc_lower for kw in ['amd', 'advanced micro', 'palomar', 'trinet', 'payroll']):
                        is_income = True

                    t_id = f"{date_val}|{desc}|{amt:.2f}" 

                    # Check for move override and apply it if it exists
                    if t_id in overrides.get('moved_transactions', {}):
                        month_key = overrides['moved_transactions'][t_id]

                    is_ignored = False
                    if t_id in overrides.get('ignored_exact', []):
                        is_ignored = True
                    else:
                        for ignored_desc in overrides.get('ignored_descriptions', []):
                            if ignored_desc and ignored_desc.lower() in desc.lower():
                                is_ignored = True
                                break

                    cat = None
                    if t_id in overrides.get('exact_mapping', {}):
                        cat = overrides['exact_mapping'][t_id]
                    else:
                        for mapped_desc, mapped_cat in overrides.get('description_mapping', {}).items():
                            if mapped_desc and mapped_desc.lower() in desc.lower():
                                cat = mapped_cat
                                break
                    
                    if not cat:
                        cat = 'Other'
                        for key in row.keys():
                            if 'category' in key.lower():
                                cat = row[key]
                                break
                        if not cat or cat.strip() == '':
                            cat = 'Uncategorized'

                    t = {
                        'date': date_val,
                        'description': desc,
                        'category': cat,
                        'amount': amt,
                        'source': os.path.basename(csv_filename),
                        'is_income': is_income
                    }
                    
                    if month_key not in monthly_data:
                        monthly_data[month_key] = {
                            'month': month_key,
                            'transactions': [],
                            'totals': {},
                            'income_total': 0.0,
                            'income_breakdown': [],
                            'expected_total': 0.0,
                            'expected_breakdown': []
                        }
                    
                    monthly_data[month_key]['transactions'].append(t)
                    if not is_ignored:
                        if is_income:
                            short_desc = get_short_income_desc(desc)
                            monthly_data[month_key]['income_total'] += amt
                            monthly_data[month_key]['income_breakdown'].append({'desc': desc, 'short_desc': short_desc, 'amount': amt})
                        elif cat == 'Expected!':
                            # Add to totals so it appears in charts like Sankey
                            monthly_data[month_key]['totals'][cat] = monthly_data[month_key]['totals'].get(cat, 0) + amt

                            display_desc = desc
                            rule_pattern = None
                            for pattern, new_name in overrides.get('expected_rename_mapping', {}).items():
                                if pattern and pattern.lower() in desc.lower():
                                    display_desc = new_name
                                    rule_pattern = pattern
                                    break

                            monthly_data[month_key]['expected_total'] += amt
                            monthly_data[month_key]['expected_breakdown'].append({'desc': display_desc, 'original_desc': desc, 'amount': amt, 'rule_pattern': rule_pattern})
                        else:
                            monthly_data[month_key]['totals'][cat] = monthly_data[month_key]['totals'].get(cat, 0) + amt
        except Exception as e:
            print(f"Skipping {csv_filename} due to error: {e}")

    all_data = [monthly_data[k] for k in sorted(monthly_data.keys(), reverse=True)] if monthly_data else []
    return all_data, overrides

def main():
    if len(sys.argv) < 2:
        print("Usage: python budget.py <csv_file1> <csv_file2> ...")
        sys.exit(1)

    csv_files = sys.argv[1:]
    BudgetHandler.csv_files = csv_files # Set class attribute for the handler

    all_data, overrides = process_files(csv_files)

    if all_data:
        generate_html(all_data, overrides)

        PORT = 8000
        while True:
            try:
                server_address = ("", PORT)
                httpd = http.server.HTTPServer(server_address, BudgetHandler)
                break
            except OSError as e:
                if e.errno in (48, 98):  # Address already in use
                    PORT += 1
                else:
                    raise
        
        print(f"\nStarting local interactive server...")
        print(f"Open http://localhost:{PORT}/report.html in your browser.")
        print("Press Ctrl+C to stop.")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nShutting down server.")
            httpd.server_close()
    else:
        print("No data processed.")

if __name__ == "__main__":
    main()
