setup:
	python buttercup/poetry2setup.py > setup.py

build: setup shiv

clean:
	rm setup.py

shiv:
	mkdir -p build
	shiv -c buttercup -o build/buttercup.pyz . --compressed
