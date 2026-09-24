.PHONY: help verify check validate figures geographic operational clean-outputs

PYTHON ?= python

help:
	@echo "make check       - run both suites below"
	@echo "make verify      - 147 checks: the data matches the paper"
	@echo "make validate    -  29 checks: the solutions are independently correct"
	@echo "make figures     - regenerate all manuscript figures, maps and tables"
	@echo "make geographic  - Section 4.1 figures only"
	@echo "make operational - Section 4.2-4.5 figures only"
	@echo ""
	@echo "Re-solving the optimization models is done through the notebooks;"
	@echo "see docs/REPRODUCTION.md. None of the targets above need a solver."

check: verify validate

verify:
	$(PYTHON) src/verify_results.py

validate:
	$(PYTHON) src/validate_solutions.py
	$(PYTHON) src/validate_solutions.py

verify-only:
	$(PYTHON) src/verify_results.py

geographic:
	$(PYTHON) src/gen_geographic_benchmark.py

operational:
	$(PYTHON) src/gen_operational_figures.py

figures: geographic operational

# Removes generated artefacts only. Never touches data/.
clean-outputs:
	rm -rf outputs/figures/geographic_paper_v1 outputs/figures/manuscript_v1
	rm -rf outputs/maps/geographic_paper_v1
	rm -rf outputs/reports/geographic_paper_v1 outputs/reports/manuscript_v1
