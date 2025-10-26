"""Calculator tool for performing mathematical operations."""

import logging
import math
from typing import Dict, Any, Optional


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _add(
    a: float,
    b: float,
) -> float:
    """Add two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b


def _subtract(
    a: float,
    b: float,
) -> float:
    """Subtract two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Difference of a and b
    """
    return a - b


def _multiply(
    a: float,
    b: float,
) -> float:
    """Multiply two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Product of a and b
    """
    return a * b


def _divide(
    a: float,
    b: float,
) -> float:
    """Divide two numbers.

    Args:
        a: First number (dividend)
        b: Second number (divisor)

    Returns:
        Quotient of a and b

    Raises:
        ValueError: If divisor is zero
    """
    if b == 0:
        logger.error("Division by zero attempted")
        raise ValueError("Cannot divide by zero")

    return a / b


def _factorial(
    a: float,
) -> int:
    """Calculate factorial of a number.

    Args:
        a: Number to calculate factorial for

    Returns:
        Factorial of the number

    Raises:
        ValueError: If number is negative or not an integer
    """
    if a < 0:
        logger.error(f"Factorial of negative number attempted: {a}")
        raise ValueError("Cannot calculate factorial of a negative number")

    if not a.is_integer():
        logger.error(f"Factorial of non-integer attempted: {a}")
        raise ValueError("Factorial requires an integer value")

    return math.factorial(int(a))


def calculator(
    operation: str,
    a: float,
    b: Optional[float] = None,
) -> Dict[str, Any]:
    """Perform mathematical calculations.

    Args:
        operation: The mathematical operation to perform
            (add, subtract, multiply, divide, factorial)
        a: First number (or the number for factorial)
        b: Second number (not used for factorial)

    Returns:
        Dictionary containing the operation, inputs, and result

    Raises:
        ValueError: If operation is invalid or inputs are invalid
    """
    if not operation or not isinstance(operation, str):
        logger.error(f"Invalid operation parameter: {operation}")
        raise ValueError("Operation must be a non-empty string")

    operation_normalized = operation.strip().lower()

    valid_operations = ["add", "subtract", "multiply", "divide", "factorial"]
    if operation_normalized not in valid_operations:
        logger.error(f"Unknown operation: {operation_normalized}")
        raise ValueError(
            f"Unknown operation: {operation}. "
            f"Valid operations are: {', '.join(valid_operations)}"
        )

    if not isinstance(a, (int, float)):
        logger.error(f"Invalid first number: {a}")
        raise ValueError("First number must be a numeric value")

    logger.info(f"Performing {operation_normalized} operation with a={a}, b={b}")

    result_value: float

    if operation_normalized == "add":
        if b is None:
            raise ValueError("Addition requires two numbers")
        result_value = _add(a, b)

    elif operation_normalized == "subtract":
        if b is None:
            raise ValueError("Subtraction requires two numbers")
        result_value = _subtract(a, b)

    elif operation_normalized == "multiply":
        if b is None:
            raise ValueError("Multiplication requires two numbers")
        result_value = _multiply(a, b)

    elif operation_normalized == "divide":
        if b is None:
            raise ValueError("Division requires two numbers")
        result_value = _divide(a, b)

    elif operation_normalized == "factorial":
        result_value = _factorial(a)

    result = {
        "operation": operation_normalized,
        "input_a": a,
        "input_b": b if b is not None else None,
        "result": result_value,
    }

    logger.info(f"Calculation result: {result_value}")

    return result
