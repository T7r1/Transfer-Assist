import os
from flask import Flask, request, jsonify, render_template
import anthropic
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

app = Flask(name)
CORS(app)

client = anthropic.Anthropic(api_key="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")

@app.route('/ask', methods=['POST'])
def send_request():
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Question not provided"}), 400

    question = data['question']

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929", # model of Claude AI
            max_tokens=1024,
            messages=[
                {"role": "user", "content": question}
            ]
        )
        response = message.content[0].text

        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if name == 'main':
    app.run(debug=True, port=5000)