# Discover Sweden

An AI-powered web app for exploring Sweden: places, scientists, inventors, food, traditions, brands and music.
Ask the AI guide a question and it answers in a few sentences, then shows related cards with a short
Wikipedia text, a picture and a link.

**Live demo:** http://13.220.103.5/ (plain HTTP; the address changes if the server is stopped and started)

## How it works

```
Browser -> nginx (port 80) -> gunicorn (127.0.0.1:5000) -> Flask app (app.py)
                                                              |-> Amazon Bedrock (Claude Haiku 4.5)
                                                              |-> Wikipedia REST API (cards)
```

- **The AI is the core of the app.** `POST /api/ask` sends the question to Claude on Amazon Bedrock.
- **The AI does not invent the cards.** It is given a curated catalogue of 45 entries (`data/entries.json`) and
  can only choose entries from that list. The picture, text and link on each card come from Wikipedia, so
  the links are real.
- **Seven categories:** Places, Scientists, Inventors, Food & drinks, Traditions & culture, Brands, Singers & bands.
- The web page (`static/index.html`) lets you browse and filter all entries and read more about each one.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | The web page |
| GET | `/api/entries` | List of all entries (id, name, category) |
| GET | `/api/card/<id>` | Details for one entry (Wikipedia text, picture, link) |
| POST | `/api/ask` | JSON `{"question": "..."}` (max 500 characters); returns an answer and up to 4 cards |

## Project structure

```
app.py              Flask backend (Bedrock call, Wikipedia cards, rate limit)
data/entries.json   Curated catalogue of 45 entries
static/index.html   Front end (HTML, CSS and JavaScript in one file)
check_titles.py     Helper that checks every Wikipedia title in entries.json
requirements.txt    Python packages
```

## Run locally

You need Python 3.12 or newer and AWS credentials that are allowed to call the Claude model in Amazon
Bedrock (region `eu-north-1`). A new AWS account must first submit the Anthropic use case form in the
Bedrock console.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000/. The model is set in `app.py` (`MODEL_ID`).

## Deploy on AWS EC2 (overview)

1. Launch an Ubuntu EC2 instance and open port 80 in its security group.
2. Attach an IAM role to the instance that allows only `bedrock:InvokeModel` for the model.
   No AWS keys are stored on the server.
3. Install nginx and Python, create a virtual environment, and run `pip install -r requirements.txt`.
4. Run the app with systemd:
   `gunicorn --workers 1 --threads 4 --bind 127.0.0.1:5000 app:app`
5. Let nginx forward port 80 to gunicorn. Overwrite the client address header so the rate limit cannot be faked:

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Security and cost

- No secrets are in this repository. `.gitignore` excludes `.env`, `*.pem`, `*.log` and the virtual environment.
- Every question to the AI costs a little, so `/api/ask` allows 20 questions per 10 minutes per visitor.
  The counter is kept in memory and is shared because the app runs with one gunicorn worker.
  It resets when the service restarts.

## Limitations

- The site uses plain HTTP, without HTTPS.
- AI answers can contain mistakes. Check the Wikipedia link on each card.
- A few Wikipedia pages have no picture (for example Nils Bohlin), so their cards show text and a link only.
- The server address changes if the EC2 instance is stopped and started, unless an Elastic IP is attached.
