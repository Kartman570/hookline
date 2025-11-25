test:
	python3 -m unittest discover -s tests -v

lint:
	ruff check .

coverage:
	coverage run -m unittest discover -s tests
	coverage report
