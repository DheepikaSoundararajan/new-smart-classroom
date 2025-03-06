from flask import Flask, render_template, request, jsonify
import os
import PyPDF2
import google.generativeai as genai
import markdown
import threading
import pyttsx3
from dotenv import load_dotenv
import time

app = Flask(__name__)

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Please set the GOOGLE_API_KEY environment variable.")

genai.configure(api_key=GOOGLE_API_KEY)

# Ensure the upload folder exists
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize AI Model
model = genai.GenerativeModel('gemini-1.5-flash-001')

# Initialize Text-to-Speech Engine
engine = pyttsx3.init()
speaking_thread = None
speaking_stop_event = None
speaking_paused = False

# Extract text from PDF
def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file."""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
    except Exception as e:
        return f"Error reading PDF: {e}"
    return text

# Generate AI Response
def generate_gemini_response(prompt, pdf_text):
    """Generates a response using Google Gemini AI."""
    full_prompt = f"{prompt}\n\nPDF Content:\n{pdf_text}"
    try:
        response = model.generate_content(full_prompt, generation_config=genai.GenerationConfig(temperature=0.4, top_p=1, top_k=32))
        return response.text
    except Exception as e:
        return f"Error generating response: {e}"

# Text-to-Speech Function
def speak_response(text, stop_event, speed=200, voice_index=0):
    """Converts text to speech in a background thread."""
    global speaking_paused
    try:
        engine.setProperty('rate', speed)
        voices = engine.getProperty('voices')
        if 0 <= voice_index < len(voices):
            engine.setProperty('voice', voices[voice_index].id)

        sentences = text.split('.')  # Split into sentences for better control
        for sentence in sentences:
            if stop_event.is_set():
                break
            while speaking_paused and not stop_event.is_set():
                time.sleep(0.1)
            if stop_event.is_set():
                break
            engine.say(sentence)
            engine.runAndWait()
    except Exception as e:
        print(f"Error during text-to-speech: {e}")

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/departments')
def departments():
    return render_template('departments.html')

@app.route('/ai_assistant', methods=['GET', 'POST'])
def ai_assistant():
    department = request.args.get('department', 'General')

    if request.method == 'POST':
        prompt = request.form['prompt']
        pdf_file = request.files['pdf_file']

        if not pdf_file or pdf_file.filename == '':
            return render_template('ai_assistant.html', error="No file uploaded.", department=department)

        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_file.filename)
        pdf_file.save(pdf_path)

        pdf_text = extract_text_from_pdf(pdf_path)
        if "error" in pdf_text.lower():
            return render_template('ai_assistant.html', error=pdf_text, department=department)

        response = generate_gemini_response(prompt, pdf_text)
        formatted_response = markdown.markdown(response)

        return render_template('ai_assistant.html', department=department, prompt=prompt, response=formatted_response, show_content=True)

    return render_template('ai_assistant.html', department=department)

if __name__ == '__main__':
    app.run(debug=True)
