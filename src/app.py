"""
Simple web UI for MTG Card Sorter.

A Flask app that provides the same functionality as the CLI, but in a browser:
- Upload card images (batch scan)
- View cards sorted by color, type, or value
- Data is stored in the same cards.json as the CLI (they share state)

Run with: python -m src.app  (or flask run)
Then open http://localhost:5000
"""

import json
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

from src.cache import _cache_dir
from src.models import CardRecord
from src.pipeline import process_image, process_images_batch
from src.scryfall_client import ScryfallClient
from src.sorting import sort_cards

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

DATA_FILE = _cache_dir() / "cards.json"
_client: ScryfallClient | None = None


def get_client() -> ScryfallClient:
    """Lazy-init Scryfall client (one per app lifetime)."""
    global _client
    if _client is None:
        _client = ScryfallClient()
    return _client


def _load_cards() -> list[CardRecord]:
    """Load cards from disk (same file as CLI)."""
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [CardRecord.from_dict(d) for d in data]
    except (json.JSONDecodeError, OSError):
        return []


def _save_cards(cards: list[CardRecord]) -> None:
    """Persist cards to disk."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in cards], f, indent=2)


HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>MTG Card Sorter</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 1rem; }
    h1 { color: #1a1a2e; }
    .mode-btns { margin: 1rem 0; }
    .mode-btns button { margin-right: 0.5rem; padding: 0.5rem 1rem; cursor: pointer; }
    .mode-btns button.active { background: #4361ee; color: white; border: none; }
    .bins { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .bin { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; background: #f8f9fa; }
    .bin h3 { margin-top: 0; font-size: 1rem; }
    .bin ul { margin: 0; padding-left: 1.2rem; }
    .bin li { margin: 0.2rem 0; }
    .upload { margin: 1rem 0; padding: 1rem; border: 2px dashed #ccc; border-radius: 8px; }
    .upload input { display: block; margin-top: 0.5rem; }
    .error { color: #c1121f; }
    .msg { color: #2d6a4f; margin: 0.5rem 0; }
  </style>
</head>
<body>
  <h1>MTG Card Sorter</h1>
  <p>Scan card images, then sort by color, type, or value.</p>

  <div class="upload">
    <label>Batch scan (multiple images):</label>
    <input type="file" id="fileInput" accept="image/*" multiple>
    <button id="scanBtn">Scan</button>
    <div id="scanMsg"></div>
  </div>

  <div class="mode-btns">
    <button data-mode="color" class="active">Color Bucket</button>
    <button data-mode="type">Card Type</button>
    <button data-mode="value">Value</button>
  </div>

  <div id="bins" class="bins"></div>

  <script>
    let cards = [];
    let mode = 'color';

    async function loadCards() {
      const r = await fetch('/api/cards');
      const data = await r.json();
      cards = data.cards || [];
      renderBins();
    }

    function renderBins() {
      if (cards.length === 0) {
        document.getElementById('bins').innerHTML = '<p>No cards. Scan images to add cards.</p>';
        return;
      }
      fetch('/api/sort?mode=' + mode)
        .then(r => r.json())
        .then(data => {
          const bins = data.bins || {};
          let html = '';
          for (const [label, items] of Object.entries(bins)) {
            html += '<div class="bin"><h3>' + label + ' (' + items.length + ')</h3><ul>';
            items.forEach(c => {
              const usd = parseFloat(c.prices_usd) || 0;
              const foil = parseFloat(c.prices_usd_foil) || 0;
              const price = Math.max(usd, foil);
              const p = price > 0 ? ' $' + price.toFixed(2) : '';
              html += '<li>' + c.name + ' (' + c.set + ')' + p + '</li>';
            });
            html += '</ul></div>';
          }
          document.getElementById('bins').innerHTML = html;
        });
    }

    document.querySelectorAll('.mode-btns button').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('.mode-btns button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        mode = btn.dataset.mode;
        renderBins();
      };
    });

    document.getElementById('scanBtn').onclick = async () => {
      const input = document.getElementById('fileInput');
      if (!input.files.length) { alert('Select images first'); return; }
      const msg = document.getElementById('scanMsg');
      msg.innerHTML = 'Scanning...';
      const form = new FormData();
      for (let i = 0; i < input.files.length; i++) form.append('images', input.files[i]);
      try {
        const r = await fetch('/api/scan', { method: 'POST', body: form });
        const data = await r.json();
        msg.innerHTML = 'Added ' + (data.added || 0) + ' card(s). ' + (data.errors?.length ? 'Errors: ' + data.errors.join('; ') : '');
        msg.className = data.errors?.length ? 'error' : 'msg';
        loadCards();
      } catch (e) {
        msg.innerHTML = 'Error: ' + e.message;
        msg.className = 'error';
      }
    };

    loadCards();
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    """Serve the main page (HTML with embedded JS)."""
    return render_template_string(HTML)


@app.route("/api/cards")
def api_cards():
    """API: return all cards as JSON."""
    cards = _load_cards()
    return jsonify({"cards": [c.to_dict() for c in cards]})


@app.route("/api/sort")
def api_sort():
    mode = request.args.get("mode", "color")
    if mode not in ("color", "type", "value"):
        mode = "color"
    cards = _load_cards()
    groups = sort_cards(cards, mode)
    bins = {k: [c.to_dict() for c in v] for k, v in groups.items()}
    return jsonify({"bins": bins})


@app.route("/api/scan", methods=["POST"])
def api_scan():
    """
    API: upload images, run OCR + Scryfall lookup, add to card list.

    Saves uploads to temp dir, processes each, then deletes temp files.
    Returns {added: N, errors: [...]}.
    """
    files = request.files.getlist("images")
    if not files:
        return jsonify({"added": 0, "errors": ["No images provided"]}), 400

    # Save temp files and process
    temp_dir = Path(tempfile.gettempdir()) / "mtg_sorter"
    temp_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, f in enumerate(files):
        if f.filename:
            ext = Path(f.filename).suffix or ".jpg"
            safe_name = f"scan_{i}{ext}"
            p = temp_dir / safe_name
            f.save(p)
            paths.append(p)

    scryfall = get_client()
    cards = _load_cards()
    new_cards, errors = process_images_batch(paths, scryfall, use_cache=True)
    cards.extend(new_cards)
    _save_cards(cards)

    # Cleanup temp files
    for p in paths:
        try:
            p.unlink()
        except OSError:
            pass

    err_msgs = [f"{p}: {e}" for p, e in errors]
    return jsonify({"added": len(new_cards), "errors": err_msgs})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
