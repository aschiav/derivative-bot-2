import os
from flask import Flask, request, render_template_string
from sympy import symbols, sympify, diff, simplify, latex
import openai

app = Flask(__name__)

# Load your OpenAI API key from environment variable
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASSISTANT_ID = os.environ.get("ASSISTANT_ID")  # optional, if using Assistant ID
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

x = symbols("x")  # symbol for derivatives

# Function to get feedback from OpenAI
def get_openai_feedback(func_str, user_prime_str):
    prompt = f"""
    You are a helpful math tutor.
    The function is f(x) = {func_str}.
    A student answered that its derivative is f'(x) = {user_prime_str}.
    1. Check if the answer is correct.
    2. Provide a step-by-step explanation of the derivative.
    3. If the answer is wrong, indicate the correct derivative.
    """
    response = openai.chat.completions.create(
        model="gpt-5.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message["content"]

# Root page with quiz form
@app.route("/", methods=["GET", "POST"])
def home():
    func_input = ""
    derivative_input = ""
    feedback = ""

    if request.method == "POST":
        func_input = request.form.get("function", "")
        derivative_input = request.form.get("derivative", "")

        try:
            f = sympify(func_input)
            f_prime = diff(f, x)
            user_prime = sympify(derivative_input)

            # Quick correctness check
            is_correct = simplify(f_prime - user_prime) == 0
            correctness = "✅ Correct!" if is_correct else "❌ Incorrect."

            # OpenAI explanation
            openai_feedback = get_openai_feedback(func_input, derivative_input)

            # Display combined feedback
            feedback = f"{correctness}<br><br>{openai_feedback.replace('\\n','<br>')}"

        except Exception as e:
            feedback = f"Error: {e}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Derivative Quiz Bot</title>
        <script type="text/javascript" async
            src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js">
        </script>
    </head>
    <body>
        <h1>Derivative Quiz</h1>
        <form method="POST">
            <label>Original function f(x):</label><br>
            <input type="text" name="function" size="40" value="{func_input}"><br><br>
            <label>Your derivative f'(x):</label><br>
            <input type="text" name="derivative" size="40" value="{derivative_input}"><br><br>
            <input type="submit" value="Check Derivative">
        </form>
        <h2>Feedback:</h2>
        <p>{feedback}</p>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
