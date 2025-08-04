from flask import Flask, jsonify, request
from flask_cors import CORS
from ticket_generator_module import generate_full_strip

app = Flask(__name__)
CORS(app)

@app.route("/api/tickets")
def get_tickets():
    try:
        count = int(request.args.get("cards", 1))  # ?cards=2 means 2 strips

        # Safeguard: limit the max to 10 strips (i.e. 60 tickets)
        if count < 1:
            count = 1
        elif count > 10:
            count = 10

        all_tickets = []
        for _ in range(count):
            strip = generate_full_strip()  # Each strip = 6 tickets
            all_tickets.extend(strip)

        return jsonify({"cards": all_tickets})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

