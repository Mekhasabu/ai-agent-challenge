import argparse
import os
import pandas as pd # type: ignore
import pdfplumber # type: ignore
import google.generativeai as genai # type: ignore
import subprocess
import sys
import re
import importlib.util
from pathlib import Path

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyBozlpXlbCkguGidDXk66YmTzoHQ5zQpDI"  # Replace with your actual API key
genai.configure(api_key=GEMINI_API_KEY)

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file using pdfplumber"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

def analyze_csv_file(csv_path):
    """Read and analyze CSV file to understand the expected output"""
    try:
        df = pd.read_csv(csv_path)
        
        # Get information about the CSV structure
        schema_info = {
            "columns": list(df.columns),
            "dtypes": df.dtypes.to_dict(),
            "sample": df.head(10).to_string(),
            "shape": df.shape
        }
        
        return df, schema_info
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None, None

def generate_parser_code(bank_name, pdf_text, csv_info, attempt=1):
    """Generate parser code using Gemini based on samples"""
    
    # Create a detailed prompt for the AI
    prompt = f"""
    You are an expert Python programmer specializing in data extraction from bank statements.
    
    Task: Create a parser for {bank_name.upper()} bank statements that extracts transaction data from PDF files.
    
    The parser should:
    1. Be implemented as a function called `parse(pdf_path)` that returns a pandas DataFrame
    2. Extract all transactions from the PDF
    3. Match the schema and format of the sample CSV data provided
    4. Handle various formats and layouts of {bank_name.upper()} bank statements
    
    Sample data from the PDF (first 2000 characters):
    ```
    {pdf_text[:2000]}
    ```
    
    Expected CSV schema:
    - Columns: {csv_info['columns']}
    - Data types: {csv_info['dtypes']}
    - Shape: {csv_info['shape']}
    
    Sample of expected CSV output (first 10 rows):
    {csv_info['sample']}
    
    Important requirements:
    - Use pdfplumber for PDF text extraction
    - Return a pandas DataFrame with the exact same columns and data types as the sample CSV
    - Handle date parsing correctly (ICICI often uses DD/MM/YYYY format)
    - Extract all transaction records
    - Handle numeric values with commas (e.g., "1,000.00" should become 1000.0)
    
    Write the complete Python code for the parser. Include only the code, no explanations.
    The code should be robust and handle potential variations in the PDF format.
    """
    
    try:
        # Use Gemini to generate code
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        response = model.generate_content(prompt)
        code = response.text
        
        # Clean up the response (remove markdown code blocks if present)
        code = re.sub(r'```python|```', '', code).strip()
        
        return code
    except Exception as e:
        print(f"Error generating code: {e}")
        return None

def test_parser(parser_path, pdf_path, expected_csv_path):
    """Test the generated parser against the sample data"""
    try:
        # Dynamically import the parser module
        spec = importlib.util.spec_from_file_location("custom_parser", parser_path)
        parser_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parser_module)
        
        # Run the parser
        result_df = parser_module.parse(pdf_path)
        
        # Read expected results
        expected_df = pd.read_csv(expected_csv_path)
        
        # Reset indices for comparison
        result_df = result_df.reset_index(drop=True)
        expected_df = expected_df.reset_index(drop=True)
        
        # Compare results
        if result_df.equals(expected_df):
            return True, "Parser test passed!"
        else:
            # Provide detailed feedback on differences
            diff = ""
            if result_df.shape != expected_df.shape:
                diff = f"Shape mismatch: Result {result_df.shape} vs Expected {expected_df.shape}"
            else:
                # Check column by column
                for col in expected_df.columns:
                    if col not in result_df.columns:
                        diff = f"Missing column: {col}"
                        break
                    if not result_df[col].equals(expected_df[col]):
                        diff = f"Column {col} doesn't match"
                        break
            
            return False, f"Parser test failed. {diff}"
            
    except Exception as e:
        return False, f"Error testing parser: {str(e)}"

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Generate bank statement parsers')
    parser.add_argument('--target', required=True, help='Bank name to generate parser for')
    args = parser.parse_args()
    
    bank_name = args.target.lower()
    base_path = f"data/{bank_name}"
    pdf_path = f"{base_path}/{bank_name}_sample.pdf"
    csv_path = f"{base_path}/{bank_name}_sample.csv"
    output_path = f"custom_parsers/{bank_name}_parser.py"
    
    # Create custom_parsers directory if it doesn't exist
    os.makedirs("custom_parsers", exist_ok=True)
    
    # Check if sample files exist
    if not os.path.exists(pdf_path):
        print(f"PDF sample file not found: {pdf_path}")
        sys.exit(1)
        
    if not os.path.exists(csv_path):
        print(f"CSV sample file not found: {csv_path}")
        sys.exit(1)
    
    # Extract data from samples
    print("Extracting data from samples...")
    pdf_text = extract_text_from_pdf(pdf_path)
    if pdf_text is None:
        print("Failed to extract text from PDF")
        sys.exit(1)
        
    csv_df, csv_info = analyze_csv_file(csv_path)
    if csv_df is None:
        print("Failed to analyze CSV file")
        sys.exit(1)
    
    print(f"PDF text extracted ({len(pdf_text)} characters)")
    print(f"CSV analyzed: {csv_info['shape']} shape with columns {csv_info['columns']}")
    
    # Attempt to generate and test parser (up to 3 attempts)
    for attempt in range(1, 4):
        print(f"\nAttempt {attempt}: Generating parser code...")
        parser_code = generate_parser_code(bank_name, pdf_text, csv_info, attempt)
        
        if not parser_code:
            print("Failed to generate parser code")
            continue
            
        # Save the generated parser
        with open(output_path, 'w') as f:
            f.write(parser_code)
        
        print(f"Parser code generated and saved to {output_path}")
        print("Testing generated parser...")
        
        success, message = test_parser(output_path, pdf_path, csv_path)
        
        if success:
            print(f"Success! Parser works correctly.")
            print(f"Parser saved to {output_path}")
            break
        else:
            print(f"Attempt {attempt} failed: {message}")
            if attempt == 3:
                print("All attempts failed. The generated parser may need manual adjustments.")
    else:
        print("Failed to generate a working parser after 3 attempts")

if __name__ == "__main__":
    main()