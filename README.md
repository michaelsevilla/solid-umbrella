# solid-umbrella

A lightweight, interactive local web application to visualize and analyze your personal finances. It parses CSV exports from your bank or credit card, categorizes transactions, and presents them in an interactive dashboard featuring month-by-month Cash Flow diagrams, Pie Charts, and sortable tables.

> **Why "Solid Umbrella"?** Because everyone needs protection for a rainy day. Just like a sturdy umbrella keeps you dry in a downpour, a solid grasp on your finances protects you from unexpected expenses. This tool provides the overarching view you need to stop leaks, build your savings, and keep your cash flow from washing away.

## Features
- **Multi-Account Support:** Feed it multiple CSVs (checking, savings, credit cards) and it will combine them into seamless monthly views.
- **Interactive Visuals:** Toggle between pie charts and Sankey "Cash Flow" diagrams to see where your money is going.
- **Dynamic Overrides:** Edit categories or ignore transactions directly in the browser. Changes are instantly saved back to your local `overrides.json` file to persist across future runs.
- **Smart Sorting:** Click table headers to sort by amount, description, or category.
- **Income Tracking:** Automatically detects payroll deposits (e.g. AMD, Palomar) and breaks them down at the top of the monthly reports.

## Prerequisites
- Python 3.6+
- An active internet connection (to load Chart.js and Plotly libraries via CDN).

## File Structure
```text
.
├── budget.py           # Main Python script that processes CSVs and serves the app
├── checking.csv        # Example: Exported bank checking account statement
├── credit-card.csv     # Example: Exported credit card statement
├── index.html          # Simple standalone budget categorizer (alternative tool)
├── overrides.json      # User-specific categorization rules and ignored transactions
├── README.md           # This documentation file
├── report.html         # The generated output dashboard (created by budget.py)
└── template.html       # HTML/JS/CSS frontend template for the dashboard
```

**Note on Ignored Files:** Our `.gitignore` intentionally excludes `*.csv`, `*.json` (like `overrides.json`), and `report.html`. We did this because these files are highly user-specific and contain private financial data. The CSVs are your personal checking and credit card statements, the overrides contain your personal custom categorization rules, and the generated report is your specific financial output dashboard.

## Usage
Run the script by passing one or more CSV files as arguments:
```bash
python budget.py checking.csv credit_card.csv
```

The script will parse your files, start a local background HTTP server, and generate `report.html`.
Open your browser and navigate to: **http://localhost:8000/report.html**

## Managing Overrides
Clicking the pencil (✏️) or the red X (❌) next to any transaction allows you to rename its category or ignore it entirely. Selecting "All Future" or "All Matching" automatically builds rules in `overrides.json` so you never have to manually categorize that vendor again.
