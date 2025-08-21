import pdfplumber
import pandas as pd
import numpy as np
import re

def parse(pdf_path: str) -> pd.DataFrame:
    """
    Parses an ICICI bank statement PDF to extract transaction data.

    Args:
        pdf_path (str): The path to the PDF bank statement file.

    Returns:
        pd.DataFrame: A pandas DataFrame containing the extracted transaction data,
                      matching the specified schema and format.
    """
    all_extracted_rows = []
    # Define the expected columns for the output DataFrame
    output_columns = ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance']

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Extract tables from the page. pdfplumber is good at detecting tabular data.
            tables = page.extract_tables()
            for table in tables:
                all_extracted_rows.extend(table)

    header_row_idx = -1
    header_indices = {}
    
    # Attempt to find the header row within all extracted rows.
    # The header is identified by the presence of key column names.
    for i, row in enumerate(all_extracted_rows):
        # Clean each cell in the row (strip whitespace, handle None)
        cleaned_row = [cell.strip() if cell else '' for cell in row]
        
        # Check for essential headers to identify a potential transaction table header
        if 'Date' in cleaned_row and 'Description' in cleaned_row and 'Balance' in cleaned_row:
            try:
                # Get the column index for each expected header
                date_idx = cleaned_row.index('Date')
                desc_idx = cleaned_row.index('Description')
                debit_idx = cleaned_row.index('Debit Amt') if 'Debit Amt' in cleaned_row else -1
                credit_idx = cleaned_row.index('Credit Amt') if 'Credit Amt' in cleaned_row else -1
                balance_idx = cleaned_row.index('Balance')
                
                # Basic sanity check for typical column order in bank statements
                if date_idx < desc_idx and balance_idx > desc_idx:
                    header_indices = {
                        'Date': date_idx,
                        'Description': desc_idx,
                        'Debit Amt': debit_idx,
                        'Credit Amt': credit_idx,
                        'Balance': balance_idx
                    }
                    header_row_idx = i
                    break  # Header found, stop searching
            except ValueError:
                # One of the expected headers (that we `.index()`ed) was not found in `cleaned_row`,
                # or an unexpected format, so this row is not the header. Continue to the next.
                continue

    transactions_data = []

    if header_row_idx != -1:
        # If a header was successfully identified, process the data rows that follow it.
        data_rows = all_extracted_rows[header_row_idx + 1:]
        
        # Determine the maximum index that we will need to access in a row,
        # to prevent IndexError for malformed or short rows.
        max_valid_idx = max(idx for idx in header_indices.values() if idx != -1)

        for row in data_rows:
            # Skip rows that are too short to contain all expected data
            if len(row) <= max_valid_idx:
                continue
            
            try:
                date_str = row[header_indices['Date']]
                description = row[header_indices['Description']]
                
                # Safely get string values for Debit Amt, Credit Amt, and Balance.
                # Use `None` if the column index is -1 (meaning the header wasn't found)
                # or if the row is unexpectedly short.
                debit_amt_str = None
                if header_indices['Debit Amt'] != -1 and len(row) > header_indices['Debit Amt']:
                    debit_amt_str = row[header_indices['Debit Amt']]
                
                credit_amt_str = None
                if header_indices['Credit Amt'] != -1 and len(row) > header_indices['Credit Amt']:
                    credit_amt_str = row[header_indices['Credit Amt']]
                
                balance_str = row[header_indices['Balance']] # Balance is a mandatory column

                # Clean and convert string values to appropriate Python types
                date = date_str.strip() if date_str else ''
                desc = description.strip() if description else ''

                def clean_and_convert_num(val_str):
                    """Helper function to clean numeric strings and convert to float."""
                    if val_str is None or str(val_str).strip() == '':
                        return np.nan
                    # Remove commas and ensure single decimal point (if multiple, take first part)
                    clean_val = str(val_str).replace(',', '').strip()
                    try:
                        return float(clean_val)
                    except ValueError:
                        return np.nan # Return NaN if conversion fails

                debit_amt = clean_and_convert_num(debit_amt_str)
                credit_amt = clean_and_convert_num(credit_amt_str)
                balance = clean_and_convert_num(balance_str)

                # Basic validation for a valid transaction row: must have a date and a numeric balance.
                if date and pd.notna(balance):
                    transactions_data.append([date, desc, debit_amt, credit_amt, balance])

            except (IndexError, TypeError):
                # Catch potential errors if a row doesn't conform to the expected structure
                # (e.g., column index out of bounds, or unexpected data types in cells)
                continue
    else:
        # This block is executed if `pdfplumber.extract_tables()` failed to identify
        # a clear tabular structure with the expected headers.
        # For this problem, we rely on table extraction given the sample PDF data structure.
        # A more complex parser would implement a text-based fallback using regex and heuristics here,
        # potentially involving coordinate analysis or sophisticated pattern matching,
        # but that goes beyond the immediate scope of clear tabular data extraction.
        print(f"Warning: Could not find a suitable table header in '{pdf_path}'. "
              "Transaction extraction might be incomplete or failed. "
              "Ensure the PDF contains clearly formatted tables with expected headers.")

    # Create a pandas DataFrame from the extracted data
    df = pd.DataFrame(transactions_data, columns=output_columns)

    # Convert data types to match the expected schema
    # Date: Convert to datetime objects first for robust parsing, then format back to string ('object' dtype)
    df['Date'] = df['Date'].apply(lambda x: pd.to_datetime(x, dayfirst=True, errors='coerce').strftime('%d-%m-%Y') if pd.notna(x) and x != '' else np.nan)
    # Ensure Description is string type
    df['Description'] = df['Description'].astype(str)

    # Convert numeric columns, coercing errors to NaN
    df['Debit Amt'] = pd.to_numeric(df['Debit Amt'], errors='coerce')
    df['Credit Amt'] = pd.to_numeric(df['Credit Amt'], errors='coerce')
    df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce')

    # Drop rows where 'Date' or 'Balance' are NaN, as these likely represent malformed rows,
    # headers/footers incorrectly parsed as data, or summary lines.
    df.dropna(subset=['Date', 'Balance'], inplace=True)
    
    # Reset index to clean up after dropping rows
    df.reset_index(drop=True, inplace=True)

    return df