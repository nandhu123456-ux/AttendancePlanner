import os
import sys

# Add the app directory to sys.path so that 'services' and 'api' modules
# can be imported directly in test files (matching existing test conventions).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))