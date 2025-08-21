# ai-agent-challenge

# Agent-as-Coder Challenge  

## 📌 Overview  
This project implements an **autonomous coding agent** that generates **custom bank statement parsers** from PDF files.  

The agent:  
- Reads a **sample PDF** and matching **CSV** for a given bank.  
- Uses **Google Gemini** to generate a parser (`custom_parsers/<bank>_parser.py`).  
- Runs a **self-correcting loop (≤3 attempts)**:  
  - Extract → Plan → Generate Code → Test → Refine  
- Validates the parser by comparing its output against the reference CSV.  
- Works for multiple banks (ICICI, SBI, HDFC, etc.) with no manual tweaks.  

---

## ⚙️ Installation  

```bash
git clone <your_repo_url>
cd ai-agent-challenge

# Install dependencies
pip install pandas pdfplumber pytest google-generativeai

-Get a Gemini API key from https://aistudio.google.com/
Replace `your-gemini-api-key-here` in `agent.py` with your actual key
Usage

Run the agent for a bank (example: ICICI):

python agent.py --target icici


Reads: data/icici/icici_sample.pdf & data/icici/icici_sample.csv

Writes: custom_parsers/icici_parser.py

Run tests:

pytest tests/test_parser.py -v


✅ Green test means the parser works correctly.
Agent Design

The agent follows a self-correcting loop:

flowchart TD
    A[Extract PDF + CSV] --> B[Plan Schema & Logic]
    B --> C[Generate Parser Code with Gemini]
    C --> D[Test Parser vs CSV]
    D -->|Pass| E[Done ✅]
    D -->|Fail| B


Extract: Reads text from sample PDF (pdfplumber) and schema from CSV.

Plan: Analyzes structure of expected output.

Generate: Uses Gemini LLM to write a parser (parse(pdf_path) -> DataFrame).

Test: Runs parser and compares result to CSV (pandas.DataFrame.equals).

Refine: If test fails, retries with improved prompt (up to 3 attempts).
