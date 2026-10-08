import pytest

from app.agent.tools import calculator, days_between


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("449 * 12 * 12 * 0.9", "58190.4"),
        ("(1.90 * 50) + 449", "544"),
        ("2 ** 10", "1024"),
        ("-5 + 3", "-2"),
        ("10 / 4", "2.5"),
        ("€1,200 * 3", "3600"),  # currency symbols and thousands separators are tolerated
    ],
)
def test_calculator(expression, expected):
    assert calculator.invoke({"expression": expression}).endswith(f"= {expected}")


@pytest.mark.parametrize(
    "expression",
    ["__import__('os').system('ls')", "open('secrets.txt')", "price * 2", "[1, 2]", "2 ** 1000", "1 / 0"],
)
def test_calculator_rejects_anything_but_arithmetic(expression):
    assert calculator.invoke({"expression": expression}).startswith("Error")


def test_days_between():
    assert days_between.invoke({"start": "2026-09-30", "end": "2026-12-31"}).startswith("92 days")
    assert days_between.invoke({"start": "2026-12-31", "end": "2026-09-30"}).startswith("-92 days")
    assert days_between.invoke({"start": "30/09/2026", "end": "2026-12-31"}).startswith("Error")
