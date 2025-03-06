from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import PyPDF2
import google.generativeai as genai
import threading
import pyttsx3
import markdown
from dotenv import load_dotenv
import time

app = Flask(__name__)

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# Set up file storage for departments
UPLOAD_FOLDER = "uploads"
DEPARTMENTS = [
    "Civil Engineering",
    "Chemical Engineering",
    "Computer Science Engineering",
    "Information Technology",
    "Electronics & Communication Engineering",
    "Electrical & Electronics Engineering"
]
for dept in DEPARTMENTS:
    os.makedirs(os.path.join(UPLOAD_FOLDER, dept), exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# AI Model
model = genai.GenerativeModel("gemini-1.5-flash-001")

# Text-to-Speech Engine
engine = pyttsx3.init()
speaking_thread = None
speaking_stop_event = None
speaking_paused = False

# Extract text from PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
    except Exception as e:
        return f"Error reading PDF: {e}"
    return text

# Generate AI Response
def generate_gemini_response(prompt, pdf_text):
    full_prompt = f"{prompt}\n\nPDF Content:\n{pdf_text}"
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Error generating response: {e}"

# Text-to-Speech Function
def speak_response(text, stop_event):
    global speaking_paused
    try:
        for sentence in text.split("."):
            if stop_event.is_set():
                break
            while speaking_paused and not stop_event.is_set():
                time.sleep(0.1)
            engine.say(sentence)
            engine.runAndWait()
    except Exception as e:
        print(f"Error during text-to-speech: {e}")

@app.route("/")
def welcome():
    return render_template("welcome.html")

@app.route("/departments")
def departments():
    return render_template("departments.html", departments=DEPARTMENTS)

@app.route("/department/<dept_name>")
def department_page(dept_name):
    department_folder = os.path.join(UPLOAD_FOLDER, dept_name)
    pdf_files = os.listdir(department_folder)
    return render_template("ai_assistant.html", department=dept_name, pdf_files=pdf_files)

@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():
    department = request.form["department"]
    pdf_file = request.files["pdf_file"]
    if pdf_file.filename == "":
        return jsonify({"status": "error", "message": "No file selected"})
    
    save_path = os.path.join(UPLOAD_FOLDER, department, pdf_file.filename)
    pdf_file.save(save_path)
    return jsonify({"status": "success", "message": "File uploaded successfully"})

@app.route("/process_pdf", methods=["POST"])
def process_pdf():
    department = request.form["department"]
    pdf_filename = request.form["pdf_filename"]
    prompt = request.form["prompt"]
    
    pdf_path = os.path.join(UPLOAD_FOLDER, department, pdf_filename)
    pdf_text = extract_text_from_pdf(pdf_path)
    
    response = generate_gemini_response(prompt, pdf_text)
    formatted_response = markdown.markdown(response, extensions=["fenced_code", "tables"])

    return jsonify({"status": "success", "response": formatted_response, "text_response": response})

@app.route("/stop_speech", methods=["POST"])
def stop_speech():
    global speaking_thread, speaking_stop_event
    if speaking_thread and speaking_thread.is_alive():
        speaking_stop_event.set()
        speaking_thread.join()
    return jsonify({"status": "stopped"})

@app.route("/pause_speech", methods=["POST"])
def pause_speech():
    global speaking_paused
    speaking_paused = not speaking_paused
    return jsonify({"status": "paused" if speaking_paused else "resumed"})

if __name__ == "__main__":
    app.run(debug=True)
