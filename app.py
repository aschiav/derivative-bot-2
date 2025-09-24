# app.py
import os, io, base64
from flask import Flask, request, render_template_string
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image
from pillow_heif import register_heif_opener

# ---- Setup ----
load_dotenv()
register_heif_opener()  # Enable PIL to open .heic/.heif

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB max upload

@app.after_request
def allow_canvas_iframe(resp):
    # Remove old X-Frame-Options if any
    resp.headers.pop("X-Frame-Options", None)
    # Allow Canvas to frame your site (update the domain to your school’s Canvas)
    resp.headers["Content-Security-Policy"] = (
        "frame-ancestors 'self' https://*.instructure.com https://canvas.stjohns.edu"
    )
    return resp

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif",
    "image/heic", "image/heif"
}

# ---- Minimal HTML (with MathJax) ----
HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Derivative Tutor — Image → GPT-4o-mini</title>
  <!-- MathJax for LaTeX -->
  <script async src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js"></script>
  <!-- Markdown + Sanitizer -->
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; }
    .card { border: 1px solid #e7e7e7; border-radius: 12px; padding: 1rem; margin-top: 1rem; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .imgprev { max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 8px; }
    pre { white-space: pre-wrap; word-wrap: break-word; }
    .muted { color: #666; font-size: .9rem; }
    button { padding: .6rem 1rem; border-radius: 10px; border: 1px solid #ddd; background: #fafafa; cursor: pointer; }
    button:hover { background: #f0f0f0; }

    /* Nicer typography for rendered Markdown */
    .prose h1, .prose h2, .prose h3 { margin: .7rem 0 .35rem; }
    .prose p { line-height: 1.6; margin: .5rem 0; }
    .prose ul, .prose ol { padding-left: 1.2rem; margin: .5rem 0; }
    .prose code { background: #f6f8fa; padding: .1rem .25rem; border-radius: 4px; }
    .prose pre { background: #f6f8fa; padding: .6rem; border-radius: 8px; overflow: auto; }
    .prose hr { border: none; border-top: 1px solid #eee; margin: 1rem 0; }
  </style>
</head>
<body>
  <h1>Derivative Tutor</h1>

  <form method="POST" enctype="multipart/form-data" class="card">
    <label>Upload a photo of your function, its derivative, and how you found the answer. The tutor will give you feedback!</label><br><br>
    <input type="file" name="equation_image" accept="image/*,.heic,.heif" required />
    <br><br>
    <button type="submit">Check my work</button>
  </form>

  {% if preview_src %}
  <div class="row">
    <div class="card">
      <h3>Uploaded image</h3>
      <img class="imgprev" src="{{ preview_src }}" alt="uploaded image preview"/>
      <p class="muted">MIME: {{ mime_type }} &middot; Size: {{ size_kb }} KB {% if converted_note %}&middot; {{ converted_note }}{% endif %}</p>
    </div>
    <div class="card">
      <h3>Feedback</h3>
      {% if error %}
        <pre>{{ error }}</pre>
      {% else %}
        <!-- We'll render Markdown → HTML here, then typeset LaTeX with MathJax -->
        <div id="model-feedback" class="prose"></div>
        <script>
          // Raw markdown from Flask (safe-encoded as JSON string)
          const rawMd = {{ response_md|tojson }};
          // Convert Markdown to HTML, then sanitize
          const html = DOMPurify.sanitize(marked.parse(rawMd), {USE_PROFILES: {html: true}});
          // Inject into the page
          const el = document.getElementById('model-feedback');
          el.innerHTML = html;
          // Ask MathJax to typeset any LaTeX in the converted content
          if (window.MathJax && MathJax.typesetPromise) {
            MathJax.typesetPromise([el]);
          }
        </script>
      {% endif %}
    </div>
  </div>
  {% endif %}
</body>
</html>
"""



def to_data_url(img_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def escape_html_keep_math(s: str) -> str:
    # Escape HTML control chars but leave $ and backslashes for LaTeX.
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace("\n", "<br>")
    )

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template_string(HTML)

    # POST
    f = request.files.get("equation_image")
    if not f:
        return render_template_string(HTML, error="Please upload an image.")

    mime = (f.mimetype or "").lower()
    if mime not in ALLOWED_MIME:
        return render_template_string(
            HTML,
            error=f"Unsupported file type: {mime}. Allowed: {', '.join(sorted(ALLOWED_MIME))}"
        )

    raw_bytes = f.read()
    if not raw_bytes:
        return render_template_string(HTML, error="Empty file uploaded.")

    preview_src = None
    converted_note = ""
    size_kb = int(len(raw_bytes) / 1024)

    # If HEIC/HEIF → convert to JPEG for the model
    try:
        if mime in {"image/heic", "image/heif"}:
            img = Image.open(io.BytesIO(raw_bytes))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=90, optimize=True)
            raw_bytes = buf.getvalue()
            mime = "image/jpeg"
            size_kb = int(len(raw_bytes) / 1024)
            converted_note = "Converted to JPEG"
    except Exception as e:
        return render_template_string(HTML, error=f"HEIC/HEIF conversion failed: {e}")

    # Build preview and data URL for the model
    data_url = to_data_url(raw_bytes, mime)
    preview_src = data_url  # reuse for on-page preview

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful math tutor. If the image contains a function and a proposed derivative, "
                        "check correctness and give a clear, step-by-step explanation. Use LaTeX for math, with $$...$$ "
                        "for display and \\(...\\) for inline."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Please check the derivative shown in this image and explain your steps. "
                                "Keep math in LaTeX."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url}
                        }
                    ],
                },
            ],
        )
        response_text = completion.choices[0].message.content or ""
        response_html = escape_html_keep_math(response_text)

        return render_template_string(
            HTML,
            response_html=response_html,
            preview_src=preview_src,
            mime_type=mime,
            size_kb=size_kb,
            converted_note=converted_note
        )

    except Exception as e:
        return render_template_string(
            HTML,
            error=f"Error calling OpenAI: {e}",
            preview_src=preview_src,
            mime_type=mime,
            size_kb=size_kb,
            converted_note=converted_note
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
