import os
from flask import Flask, request, render_template_string, jsonify
from sympy import symbols, sympify, diff, simplify

app = Flask(__name__)

x = symbols("x")  # global symbol for derivatives

# Root page with form
@app.route("/", methods=["GET", "POST"])
def home():
    feedback = ""
    func_input = ""
    derivative_input = ""
    
    if request.method == "POST":
        func_input = request.form.get("function", "")
        derivative_input = request.form.get("derivative", "")
        
        try:
            f = sympify(func_input)
            f_prime = diff(f, x)
            user_prime = sympify(derivative_input)
            
            # Check correctness
            if simplify(f_prime - user_prime) == 0:
                feedback = "✅ Correct!"
            else:
                feedback = f"❌ Incorrect. Correct derivative: {f_prime}"
                
            # Optionally, could also generate natural language explanation using OpenAI
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
