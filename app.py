from flask import Flask, jsonify, request
from flask_cors import CORS
from ticket_generator_module import generate_full_strip

app = Flask(__name__)
CORS(app)

@app.route("/api/tickets")
def get_tickets():
    try:
        count = int(request.args.get("cards", 1))  # from ?cards=2
        all_tickets = []

        for _ in range(count):
            strip = generate_full_strip()  # generates 6 tickets per card
            all_tickets.extend(strip)      # flatten all into one list

        return jsonify(all_tickets)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
