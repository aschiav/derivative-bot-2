import os
from flask import Flask, request, jsonify
from sympy import symbols, sympify, diff, latex
import openai

app = Flask(__name__)

# Load your API key from environment variable
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASSISTANT_ID = os.environ.get("ASSISTANT_ID")  # Your Assistant ID
if not OPENAI_API_KEY or not ASSISTANT_ID:
    raise RuntimeError("Missing OPENAI_API_KEY or ASSISTANT_ID")

openai.api_key = OPENAI_API_KEY

# Minimal route
@app.route("/derive", methods=["POST"])
def derive():
    data = request.get_json()
    func_str = data.get("function")
    
    if not func_str:
        return jsonify({"error": "No function provided"}), 400
    
    try:
        x = symbols('x')
        f = sympify(func_str)          # Convert string to symbolic expression
        f_prime = diff(f, x)           # Compute derivative
        f_prime_latex = latex(f_prime) # Convert to LaTeX
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Optionally: send to OpenAI Assistant for formatting or explanations
    # For now, just return the LaTeX derivative
    return jsonify({
        "input": func_str,
        "derivative": f_prime_latex
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
