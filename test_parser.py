
import pytest # type: ignore
import pandas as pd # type: ignore
import importlib.util
from pathlib import Path
from pandas.testing import assert_frame_equal
import os


def load_parser(bank_name: str):
    """Dynamically import the parser module for a given bank."""
    parser_path = Path(f"custom_parsers/{bank_name}_parser.py")
    if not parser_path.exists():
        pytest.skip(f"No parser found for {bank_name}, run agent.py first")

    spec = importlib.util.spec_from_file_location("parser_module", parser_path)
    parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_module)

    if not hasattr(parser_module, "parse"):
        raise AttributeError("Generated parser does not implement parse(pdf_path)")
    return parser_module


# Discover banks from data/ folder
banks = [d for d in os.listdir("data") if os.path.isdir(f"data/{d}")]


@pytest.mark.parametrize("bank_name", banks)
def test_parser(bank_name):
    """Test that the generated parser matches the sample CSV exactly."""
    pdf_path = Path(f"data/{bank_name}/{bank_name}_sample.pdf")
    csv_path = Path(f"data/{bank_name}/{bank_name}_sample.csv")

    parser_module = load_parser(bank_name)
    result_df = parser_module.parse(str(pdf_path)).reset_index(drop=True)
    expected_df = pd.read_csv(csv_path).reset_index(drop=True)

    # Shape + schema
    assert result_df.shape == expected_df.shape, f"Shape mismatch: {result_df.shape} vs {expected_df.shape}"
    assert list(result_df.columns) == list(expected_df.columns), f"Column mismatch: {result_df.columns} vs {expected_df.columns}"

    # Detailed comparison (ignoring dtype differences)
    assert_frame_equal(result_df, expected_df, check_dtype=False)
