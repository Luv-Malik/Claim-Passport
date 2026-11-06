"""Production entry point, for example:  gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app"""
from claimpassport.api import create_app

app = create_app()
