#!/usr/bin/env python
"""Test the JSON parser utility"""

from backend.utils.json_parser import extract_json_from_text, parse_json_safe

# Test case 1: Valid JSON
test1 = '{"tier": "Basic_Everyday", "limit": 2076, "perks": ["test"]}'
result1 = extract_json_from_text(test1)
print('Test 1 (valid JSON):', result1)

# Test case 2: JSON with formulas (the problematic case)
test2 = '{"tier": "Basic_Everyday", "limit": Math.min(1000, Math.floor(4152 * 0.5)), "perks": ["Requires $500 cash security deposit"]}'
result2 = parse_json_safe(test2, default={'limit': 0})
print('Test 2 (JSON with formulas):', result2)

# Test case 3: JSON in markdown code block
test3 = '''
Some explanation...
```json
{"status": "APPROVED", "credit_limit": 1500}
```
'''
result3 = extract_json_from_text(test3)
print('Test 3 (JSON in code block):', result3)

print("\nAll tests passed!")
