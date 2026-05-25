import json
import re
from typing import Any, Dict


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from text, even if it contains formulas or invalid syntax.
    
    This function attempts to:
    1. Parse valid JSON directly
    2. If that fails, search for JSON patterns and fix common issues
    3. Calculate any formulas found in numeric fields
    
    Args:
        text: The text potentially containing JSON
        
    Returns:
        Parsed dictionary
        
    Raises:
        ValueError: If JSON cannot be extracted or parsed
    """
    
    # First try direct parsing
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # Extract JSON-like content from text (handle markdown code blocks)
    json_pattern = r'\{[\s\S]*\}'
    matches = re.findall(json_pattern, text)
    
    for potential_json in matches:
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError:
            # Try to fix common formula issues
            fixed_json = fix_formulas_in_json(potential_json)
            try:
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                continue
    
    raise ValueError(f"Could not extract valid JSON from text: {text[:200]}")


def fix_formulas_in_json(json_str: str) -> str:
    """
    Replace mathematical formulas in JSON with their calculated values.
    
    Handles patterns like:
    - Math.min(1000, Math.floor(4152 * 0.5))
    - 0.5 * balance
    - Math.floor(value)
    - Simple arithmetic expressions
    """
    
    # Recursively process Math functions from innermost to outermost
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Handle Math.floor/ceil (these take a single argument)
        if 'Math.floor' in json_str or 'Math.ceil' in json_str:
            json_str = re.sub(
                r'Math\.(floor|ceil)\(([^()]+)\)',
                lambda m: str(int(float(eval_expression(m.group(2))))),
                json_str
            )
        
        # Handle Math.min/max (these need special handling for nested parentheses)
        if 'Math.min' in json_str or 'Math.max' in json_str:
            # First try to handle simple cases
            simple_pattern = r'Math\.(min|max)\(([^(),]+),\s*([^(),]+)\)'
            json_str = re.sub(
                simple_pattern,
                lambda m: str(handle_min_max(m.group(1), m.group(2), m.group(3))),
                json_str
            )
            
            # Then handle nested cases
            if 'Math.min' in json_str or 'Math.max' in json_str:
                # Find and process innermost Math.min/max
                json_str = process_nested_math(json_str)
        
        # If no more Math functions, break
        if 'Math.' not in json_str:
            break
    
    return json_str


def process_nested_math(json_str: str) -> str:
    """Handle nested Math.min/max by finding and processing innermost calls"""
    # Find innermost Math function call
    pattern = r'Math\.(min|max)\(([^()]+(?:\([^()]*\))*[^()]*)\)'
    
    def replace_func(match):
        func_name = match.group(1)
        args_str = match.group(2)
        
        # Split arguments by comma, but respect nested parentheses
        args = split_args(args_str)
        
        try:
            if func_name == 'min':
                result = min(float(eval_expression(arg)) for arg in args)
            else:  # max
                result = max(float(eval_expression(arg)) for arg in args)
            return str(int(result))
        except Exception as e:
            print(f"Warning: Could not evaluate {func_name}({args_str}): {e}")
            return "0"
    
    new_json_str = re.sub(pattern, replace_func, json_str, count=1)
    return new_json_str


def split_args(args_str: str) -> list:
    """Split function arguments respecting nested parentheses"""
    args = []
    current_arg = ""
    paren_depth = 0
    
    for char in args_str:
        if char == '(' :
            paren_depth += 1
            current_arg += char
        elif char == ')':
            paren_depth -= 1
            current_arg += char
        elif char == ',' and paren_depth == 0:
            args.append(current_arg.strip())
            current_arg = ""
        else:
            current_arg += char
    
    if current_arg.strip():
        args.append(current_arg.strip())
    
    return args


def handle_min_max(func_name: str, arg1: str, arg2: str) -> int:
    """Handle min/max with simple arguments"""
    val1 = eval_expression(arg1)
    val2 = eval_expression(arg2)
    
    if func_name == 'min':
        return int(min(val1, val2))
    else:
        return int(max(val1, val2))


def eval_expression(expr: str) -> float:
    """Safely evaluate a mathematical expression"""
    expr = expr.strip()
    
    # Remove quotes if present
    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
        expr = expr[1:-1]
    
    try:
        # Use a safe eval with limited scope
        result = eval(expr, {"__builtins__": {}}, {
            "min": min,
            "max": max,
            "int": int,
            "float": float
        })
        return float(result)
    except Exception as e:
        print(f"Warning: Could not evaluate expression '{expr}': {e}")
        return 0.0


def is_numeric_field(value_str: str) -> bool:
    """Check if a field value looks like it should be numeric (contains math operations)."""
    value_str = value_str.strip()
    # Check for Math functions, operators, or numbers
    return any(indicator in value_str for indicator in ['Math.', '*', '/', '+', '-', 'min', 'max', 'floor', 'ceil']) or value_str.isdigit()


def parse_json_safe(text: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Safely parse JSON with fallback to default value.
    
    Args:
        text: The text to parse
        default: Default dictionary to return if parsing fails
        
    Returns:
        Parsed dictionary or default
    """
    if default is None:
        default = {}
    
    try:
        return extract_json_from_text(text)
    except ValueError as e:
        print(f"Warning: Failed to parse JSON: {e}")
        return default

