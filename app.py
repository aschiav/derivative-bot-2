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

def ask_assistant_explain(func_str):
    response = openai.chat.completions.create(
        model="gpt-5.1-mini",  # or another model
        messages=[
            {"role": "system", "content": "You are a math tutor."},
            {"role": "user", "content": f"Explain step by step how to take the derivative of {func_str}."}
        ],
        temperature=0
    )
    return response.choices[0].message["content"]


# Minimal route
@app.route("/")
def home():
    return "Derivative bot is running! Use POST /derive to get derivatives."


@app.route("/derive", methods=["POST"])
def derive():
    data = request.get_json()
    func_str = data.get("function")
    
    if not func_str:
        return jsonify({"error": "No function provided"}), 400
    
    try:
        x = symbols('x')
        f = sympify(func_str)
        f_prime = diff(f, x)
        f_prime_latex = latex(f_prime)

        # --- OpenAI API call ---
        explanation = ask_assistant_explain(func_str)

    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "input": func_str,
        "derivative": f_prime_latex,
        "explanation": explanation
    })


@app.route("/test", methods=["GET"])
def test():
    return '''
        <form action="/derive" method="post">
            Function: <input name="function" value="x**2 + 3*x + 5">
            <input type="submit">
        </form>
    '''


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
