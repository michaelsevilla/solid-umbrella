import sys
import os
import json
import tempfile
import unittest
import shutil
from unittest.mock import patch

# Add parent directory to the path so we can import budget.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import budget

class TestBudgetApp(unittest.TestCase):
    def shortDescription(self):
        # Suppress default docstring printing so we can perfectly format it in __str__
        return None
        
    def __str__(self):
        # Extract the docstring (or method name as fallback)
        doc = self._testMethodDoc or self._testMethodName
        doc = doc.strip().split('\n')[0]
        
        # Calculate dynamic padding to right-align the result
        term_width = shutil.get_terminal_size((80, 20)).columns
        pad = max(1, term_width - len(doc) - 10)
        return f"{doc} {'.' * pad}"

    def setUp(self):
        # Save our current directory so we can safely return to it later
        self.original_cwd = os.getcwd()
        
        # Setup an isolated temporary directory for file operations
        self.temp_dir = tempfile.TemporaryDirectory()
        self.script_dir = self.temp_dir.name
        
        # Strictly sandbox the test by moving into the temporary directory
        os.chdir(self.script_dir)
        
        # Create a mock CSV file
        self.csv_path = os.path.join(self.script_dir, 'data.csv')
        with open(self.csv_path, 'w', encoding='utf-8') as f:
            f.write("Date,Description,Amount,Category\n")
            f.write("01/01/2026,Target,50.00,Shopping\n")
            f.write("01/15/2026,TRINET PAYROLL,1000.00,\n")
            f.write("01/20/2026,SD GAS,100.00,Expected!\n")
            
        # Create a mock overrides.json
        self.overrides_path = os.path.join(self.script_dir, 'overrides.json')
        self.overrides = {
            'description_mapping': {'Target': 'Groceries'},
            'ignored_descriptions': [],
            'ignored_exact': []
        }
        with open(self.overrides_path, 'w', encoding='utf-8') as f:
            json.dump(self.overrides, f)

    def tearDown(self):
        # Step out of the sandbox before destroying it
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    @patch('sys.stdout')
    @patch('budget.generate_html')
    @patch('budget.http.server.HTTPServer')
    @patch('budget.os.path.abspath')
    def test_csv_parsing_logic(self, mock_abspath, mock_server, mock_generate, mock_stdout):
        # Verifies that CSV files are correctly parsed, categories mapped, and income/expected totals are calculated.
        
        # Trick budget.py into thinking it lives in our temporary directory
        mock_abspath.return_value = os.path.join(self.script_dir, 'budget.py')
        
        test_args = ['budget.py', self.csv_path]
        with patch.object(sys, 'argv', test_args):
            budget.main()
            
        # Verify HTML generation was called and intercept the data payload
        self.assertTrue(mock_generate.called)
        all_data, _ = mock_generate.call_args[0]
        
        self.assertEqual(len(all_data), 1)
        month_data = all_data[0]
        self.assertEqual(month_data['month'], '2026-01')
        
        # Verify categorization override applied correctly (Target -> Groceries)
        target_tx = next(t for t in month_data['transactions'] if t['description'] == 'Target')
        self.assertEqual(target_tx['category'], 'Groceries')
        self.assertEqual(month_data['totals']['Groceries'], 50.0)
        
        # Verify Income auto-detection
        self.assertEqual(month_data['income_total'], 1000.0)
        
        # Verify 'Expected!' expense exclusion from normal totals
        self.assertEqual(month_data['expected_total'], 100.0)

    @patch('sys.stdout')
    @patch('budget.os.path.abspath')
    def test_advanced_overrides(self, mock_abspath, mock_stdout):
        # Verifies advanced override features like moving and renaming transactions.
        mock_abspath.return_value = os.path.join(self.script_dir, 'budget.py')

        # 1. Test the get_short_income_desc helper function directly
        self.assertEqual(budget.get_short_income_desc("ADVANCED MICRO D PAYROLL PPD ID: 123"), "ADVANCED MICRO D")
        self.assertEqual(budget.get_short_income_desc("Some other income"), "Some other income")
        self.assertEqual(budget.get_short_income_desc("payment from client"), "payment from client")

        # 2. Setup advanced overrides for moving and renaming
        self.overrides['moved_transactions'] = {
            "01/01/2026|Target|50.00": "2025-12"
        }
        self.overrides['expected_rename_mapping'] = {
            "SD GAS": "Gas Bill"
        }
        with open(self.overrides_path, 'w', encoding='utf-8') as f:
            json.dump(self.overrides, f)

        # 3. Run the file processing logic
        all_data, _ = budget.process_files([self.csv_path])

        # 4. Verify the 'move' override was applied
        jan_data = next((d for d in all_data if d['month'] == '2026-01'), None)
        self.assertIsNotNone(jan_data)
        self.assertNotIn('Groceries', jan_data['totals'])

        dec_data = next((d for d in all_data if d['month'] == '2025-12'), None)
        self.assertIsNotNone(dec_data)
        self.assertEqual(len(dec_data['transactions']), 1)
        self.assertEqual(dec_data['transactions'][0]['description'], 'Target')
        self.assertEqual(dec_data['totals']['Groceries'], 50.0)

        # 5. Verify the 'rename' override was applied to expected expenses
        gas_tx_breakdown = next(exp for exp in jan_data['expected_breakdown'] if exp['original_desc'] == 'SD GAS')
        self.assertEqual(gas_tx_breakdown['desc'], 'Gas Bill')

    @patch('sys.stdout')
    @patch('budget.os.path.abspath')
    def test_html_generation(self, mock_abspath, mock_stdout):
        # Ensures that the HTML report is properly generated with the provided data and overrides.
        
        mock_abspath.return_value = os.path.join(self.script_dir, 'budget.py')
        template_path = os.path.join(self.script_dir, 'template.html')
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write("<html>__DATA_JSON__ and __OVERRIDES_JSON__</html>")
            
        budget.generate_html([{"month": "2026-01"}], {})
        
        self.assertTrue(os.path.exists('report.html'))
        os.remove('report.html')

if __name__ == '__main__':
    unittest.main()
