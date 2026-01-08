"""
Enable running the package with: python -m summarizer

Syntax notes:
- When you run `python -m summarizer`, Python looks for __main__.py in that package
- This file is the entry point for `python -m <package>` invocations
- It's separate from __init__.py (which runs on import) and main.py (which defines the logic)

The pattern:
- __init__.py  -> runs when someone does `import summarizer`
- __main__.py  -> runs when someone does `python -m summarizer`
- main.py      -> contains the actual main() function and CLI logic

Why separate these?
- Keeps concerns separate (import-time vs. execution-time)
- Allows main.py to be imported without side effects
- Standard Python convention for runnable packages
"""

from .main import main

# Call main() and exit with its return code
# Using raise SystemExit is equivalent to sys.exit() but doesn't require importing sys
raise SystemExit(main())
