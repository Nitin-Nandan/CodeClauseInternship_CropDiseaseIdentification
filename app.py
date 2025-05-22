# CRITICAL SECTION: MUST BE AT THE VERY TOP (BEFORE ALL IMPORTS)
# ==============================================
import os
import sys
import time  # For deletion delay

# Set environment variables FIRST
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logs
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN messages

# Disable Flask and Werkzeug logging
import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('flask.app').setLevel(logging.ERROR)
# ==============================================
# CRITICAL SECTION ENDED

from flask import Flask, render_template, request, url_for, after_this_request
from keras.saving import load_model # For load_model
from keras.utils import load_img, img_to_array # For image preprocessing
import numpy as np
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure upload folder INSIDE static for image display
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load class names from dataset
dataset_path = 'PlantVillage'
class_names = sorted([d for d in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, d))])

# Disease info dictionary
disease_info = {
    'Pepper__bell___Bacterial_spot': {
        'description': 'Bacterial spot causes leaf and fruit lesions in pepper plants.',
        'prevention': 'Use disease-free seeds, practice crop rotation, apply copper-based fungicides.'
    },
    'Pepper__bell___healthy': {
        'description': 'Healthy pepper plant with no signs of disease.',
        'prevention': 'Maintain good growing conditions and regular monitoring.'
    },
    'Potato___Early_blight': {
        'description': 'Early blight causes concentric ring spots on potato leaves.',
        'prevention': 'Remove infected leaves, ensure proper spacing, use fungicides.'
    },
    'Potato___healthy': {
        'description': 'Healthy potato plant with vigorous growth.',
        'prevention': 'Continue proper irrigation and soil management.'
    },
    'Potato___Late_blight': {
        'description': 'Late blight leads to rapid plant destruction in humid conditions.',
        'prevention': 'Destroy infected plants, use resistant varieties, avoid overhead watering.'
    },
    'Tomato_Bacterial_spot': {
        'description': 'Bacterial spot creates small water-soaked lesions on tomato leaves.',
        'prevention': 'Use pathogen-free seeds, practice sanitation, apply bactericides.'
    },
    'Tomato_Early_blight': {
        'description': 'Early blight causes target-pattern lesions on lower leaves.',
        'prevention': 'Stake plants for air circulation, remove diseased leaves.'
    },
    'Tomato_healthy': {
        'description': 'Healthy tomato plant showing normal growth patterns.',
        'prevention': 'Maintain balanced nutrition and pest control.'
    },
    'Tomato_Late_blight': {
        'description': 'Late blight causes rapid defoliation and fruit rot.',
        'prevention': 'Apply fungicides preventively, remove volunteer plants.'
    },
    'Tomato_Leaf_Mold': {
        'description': 'Leaf mold appears as pale green or yellowish spots.',
        'prevention': 'Reduce humidity, improve ventilation, use fungicides.'
    },
    'Tomato_Septoria_leaf_spot': {
        'description': 'Septoria causes small circular spots with gray centers.',
        'prevention': 'Remove infected leaves, avoid overhead irrigation.'
    },
    'Tomato_Spider_mites_Two_spotted_spider_mite': {
        'description': 'Spider mites cause stippling and webbing on leaves.',
        'prevention': 'Use miticides, maintain humidity, introduce predatory mites.'
    },
    'Tomato__Target_Spot': {
        'description': 'Target spot creates concentric lesions on leaves and fruits.',
        'prevention': 'Practice crop rotation, use fungicide sprays.'
    },
    'Tomato__Tomato_mosaic_virus': {
        'description': 'Mosaic virus causes mottled leaves and stunted growth.',
        'prevention': 'Use virus-free seeds, control aphid vectors.'
    },
    'Tomato__Tomato_YellowLeaf__Curl_Virus': {
        'description': 'Yellow leaf curl causes upward curling and yellowing.',
        'prevention': 'Use resistant varieties, control whitefly populations.'
    }
}

# Load model with error handling
MODEL_PATH = 'crop_disease_model.keras'
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model file '{MODEL_PATH}' not found.")
model = load_model(MODEL_PATH)

# Confidence threshold
CONFIDENCE_THRESHOLD = 0.65
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

@app.route('/', methods=['GET', 'POST'])
def index():
    prediction = None
    error = None
    uploaded_img_url = None
    file_path = None
    disease_details = None

    if request.method == 'POST':
        if 'file' not in request.files:
            error = "No file uploaded"
            return render_template('index.html', prediction=prediction, error=error, uploaded_img_url=uploaded_img_url, disease_details=disease_details)

        file = request.files['file']
        if file.filename == '':
            error = "No file selected"
            return render_template('index.html', prediction=prediction, error=error, uploaded_img_url=uploaded_img_url, disease_details=disease_details)

        if file and allowed_file(file.filename):
            try:
                # Validate file size (max 2MB)
                file.seek(0, os.SEEK_END)
                file_length = file.tell()
                file.seek(0)
                if file_length > MAX_FILE_SIZE:
                    error = "File too large. Please upload an image smaller than 2MB."
                    return render_template('index.html', prediction=prediction, error=error, uploaded_img_url=uploaded_img_url, disease_details=disease_details)

                # Save uploaded file
                filename = secure_filename(file.filename)
                unique_filename = f"{os.urandom(8).hex()}_{filename}"
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                file.save(file_path)
                uploaded_img_url = url_for('static', filename=f'uploads/{unique_filename}')

                # Preprocess and predict
                img = load_img(file_path, target_size=(224, 224))
                img_array = img_to_array(img) / 255.0
                img_array = np.expand_dims(img_array, axis=0)

                pred = model.predict(img_array)[0]
                pred_prob = float(np.max(pred))
                pred_class = class_names[np.argmax(pred)]

                # Confidence threshold logic
                if pred_prob < CONFIDENCE_THRESHOLD:
                    prediction = f"Uncertain prediction ({pred_prob*100:.1f}% confidence). Consult an expert."
                    disease_details = {
                        'description': 'The model is not confident in this prediction.',
                        'prevention': 'Please try another image or consult an agricultural expert.'
                    }
                else:
                    prediction = f"Predicted Disease: {pred_class} ({pred_prob*100:.1f}% confidence)"
                    disease_details = disease_info.get(pred_class, {
                        'description': 'No detailed information available.',
                        'prevention': 'General advice: Maintain plant health and consult agricultural experts.'
                    })

            except Exception:
                error = "Error processing image. Please try again."
        else:
            error = "Invalid file type. Please upload an image (JPEG, PNG)"

    # Delete the uploaded image 1 second after the page loads
    if file_path and os.path.exists(file_path):
        @after_this_request
        def delete_file(response):
            def cleanup():
                time.sleep(1)  # Give browser time to load the image
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            from threading import Thread
            Thread(target=cleanup).start()
            return response

    return render_template('index.html', prediction=prediction, error=error, uploaded_img_url=uploaded_img_url, disease_details=disease_details)

import webbrowser
import threading

if __name__ == '__main__':
    HOST = '127.0.0.1'
    PORT = 5000
    print(f"\n🌱 Crop Disease Identification System")
    print(f"🔗 Local URL: http://{HOST}:{PORT}")
    print("🛑 Press CTRL+C to stop\n")

    def open_browser():
        webbrowser.open_new(f"http://{HOST}:{PORT}")

    threading.Timer(1.5, open_browser).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)

