
from flask import Flask, jsonify, request
from flask_cors import CORS
from ticket_generator_module import generate_full_strip

app = Flask(__name__)
CORS(app)

@app.route("/api/tickets")
def get_tickets():
    try:
        count = int(request.args.get("cards", 1))
        all_cards = []
        for _ in range(count):
            strip = generate_full_strip()
            all_cards.append(strip)
        return jsonify(all_cards)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
