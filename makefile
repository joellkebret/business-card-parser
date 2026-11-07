PYTHON ?= python

.PHONY: parser test memory-check clean
parser:
	$(PYTHON) scripts/build_native.py

test: parser
	$(PYTHON) -m pytest

memory-check:
	$(PYTHON) scripts/check_native_memory.py

clean:
	$(PYTHON) scripts/build_native.py --clean
