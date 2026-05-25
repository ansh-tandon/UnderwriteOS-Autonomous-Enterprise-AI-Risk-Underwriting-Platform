import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.graph.pipeline import graph
    print("Graph compiled successfully!")
except Exception as e:
    print(f"Error compiling graph: {e}")
