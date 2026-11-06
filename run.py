"""Start the app:  python run.py   (then open http://127.0.0.1:5000)"""
import os

from claimpassport.api import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=False)
