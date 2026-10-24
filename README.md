# USCF Tournament Sequence Finder

1. Put `app.py` and `index.html` in the same folder.
2. Run `python app.py` and open http://localhost:8000
3. Type letters (e.g. W, U, A), enter USCF member IDs, click Fetch histories.

You can also skip the server: `python app.py --ids 12743305 12345678 --out history.csv`, then load the CSV in the page.

Matching rule: a player's events sorted by date must contain consecutive tournaments starting with your letters in order, with none in between.
