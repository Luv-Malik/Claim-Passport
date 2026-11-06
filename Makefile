.PHONY: run test assets demo-change reset
run:            ## start the app at http://127.0.0.1:5000
	python run.py
test:           ## run all automated tests
	python -m unittest discover -s tests -t . -v
assets:         ## re-create the sample banner and PDF
	python scripts/make_sample_assets.py
demo-change:    ## simulate a price change (needs the app running)
	python scripts/demo_source_change.py
reset:          ## delete the local database and uploads (demo data comes back on next start)
	rm -f data/claimpassport.db && rm -rf data/uploads
