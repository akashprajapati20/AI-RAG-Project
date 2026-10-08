"""Tools the agent can call through Gemini function calling."""

import ast
import operator
import re
from datetime import date

from langchain_core.tools import tool

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression such as "449 * 12 * 0.9" or "(1.90 * 50) + 449".
    Supports + - * / ** % and parentheses. Use it for every price, total or quantity calculation."""
    # Models often write "€1,200 * 3"; drop currency symbols and thousands separators.
    cleaned = re.sub(r"[€$£]", "", expression)
    cleaned = re.sub(r"(?<=\d),(?=\d{3}\b)", "", cleaned)
    try:
        value = _evaluate(ast.parse(cleaned, mode="eval").body)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError) as e:
        return f"Error: {e}"
    value = round(value, 6)
    return f"{expression} = {int(value) if value == int(value) else value}"


def _evaluate(node: ast.AST) -> float:
    """Walk the parsed expression allowing only numbers and arithmetic. Never eval(): the input
    comes from the model, which may be steered by text inside retrieved documents."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        return _OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.operand))
    raise ValueError(f"only numbers and + - * / ** % ( ) are allowed, got {type(node).__name__}")


@tool
def days_between(start: str, end: str) -> str:
    """Count the days from `start` to `end` (both YYYY-MM-DD). Negative if `end` is earlier.
    Use it for any "how long until / since" question instead of counting days yourself."""
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError as e:
        return f"Error: {e}. Use YYYY-MM-DD dates."
    return f"{days} days from {start} to {end}"


@tool
def search_knowledge_base(query: str) -> str:
    """Search Brindlewave's internal documents again. Call this only when the numbered sources
    you already have don't contain something you need; use a specific query, e.g.
    "API rate limit Growth plan". New results are added as new numbered sources."""
    # Executed by the graph's tools node instead, because its results must be numbered and
    # added to the agent's sources (see nodes.run_tools).
    raise NotImplementedError


LOCAL_TOOLS = {t.name: t for t in (calculator, days_between)}
ANSWER_TOOLS = [search_knowledge_base, calculator, days_between]  # grounded answers
GENERAL_TOOLS = [calculator, days_between]  # small talk / pure calculation
