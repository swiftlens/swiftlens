#!/bin/bash
# Upload to TestPyPI
source venv_publish/bin/activate
python -m twine upload --repository testpypi dist/swiftlens-0.0.9*