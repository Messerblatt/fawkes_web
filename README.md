# Fawkes Web Interface

Flask wrapper for [Fawkes](https://github.com/Shawn-Shan/fawkes), the privacy-preserving tool that protects images against facial recognition systems.


## Overview


![Demonstrating Fawkes on an Image of Obama](/images/obama_cloakes.png)


Fawkes is a privacy tool that applies imperceptible modifications to images to protect them against unauthorized facial recognition systems. It "cloaks" faces in images, making them unrecognizable to facial recognition models while remaining visually unchanged to human observers.

This repo contains a Flask wrapper for just that. The Web Interface provides an easy-to-use graphical interface for the Fawkes image cloaking system. Upload your images through a simple drag-and-drop interface and apply privacy-preserving modifications to protect against unauthorized facial recognition.

**Tested on Python3.8.20**

## Installation

### 1. Clone this repository

```bash

git clone https://github.com/Messerblatt/fawkes_web
cd fawkes-web-app

```

### 2. Install Python dependencies

```bash

pip install -r requirements.txt

```

Keep in mind that the use of a virtual environment is strongly advised.

### 3. Set up Fawkes

Clone the original Fawkes repository into the project:

Ensure the following file structure:

```
.
├── app.py
├── fawkes/
│   ├── __init__.py
│   ├── __main__.py
│   ├── protection.py
│   ├── utils.py
│   └── ...
├── images/
├── templates/
│   └── index.html
├── requirements.txt
└── README.md

```

## Usage

### Starting the server

Run the Flask application:

```bash

python app.py

```

Or use the provided run script:

```bash

python run_server.py

```

The server will start on `http://localhost:5000`

### Using the web interface

1. **Upload an image**: Drag and drop an image or click "Select Image"
2. **Choose cloaking mode**:
   - **Low**: Fastest, minimal protection (CPU/GPU)
   - **Mid**: Balanced protection and speed (GPU required)
   - **High**: Maximum protection, slower (GPU required)
3. **Start cloaking**: Click "Start Cloaking" and monitor progress in the console
4. **Download**: Once complete, download your cloaked image

### Supported image formats

- PNG
- JPEG/JPG
- GIF
- BMP

Maximum file size: 16MB

## How Fawkes Works

Fawkes adds pixel-level perturbations to images that are invisible to the human eye but cause facial recognition models to misidentify faces. These "cloaks" are specifically designed to:

- Remain imperceptible to humans
- Persist through image compression and social media uploads
- Protect against feature extraction by facial recognition systems

For more technical details, see the [original Fawkes repository](https://github.com/Shawn-Shan/fawkes).

## Cloaking Modes

### Low Mode
- Fastest processing
- Basic protection
- Works on CPU
- Recommended for quick tests

### Mid Mode
- Balanced protection
- Moderate processing time
- Requires GPU
- Good for general use

### High Mode
- Maximum protection
- Longest processing time
- Requires GPU
- Recommended for high-security needs

## GPU Support

The application automatically detects GPU availability:

- **With GPU**: All three modes (Low, Mid, High) are available
- **Without GPU**: Only Low mode is available

To enable GPU support, ensure you have:
- CUDA-compatible GPU
- Appropriate CUDA drivers
- TensorFlow with GPU support: `pip install tensorflow-gpu`

## Output Files

Adhering to Fawke's principles of privacy, the app will purge every image from the server as soon as the cloaking is finished.

## Performance Tips

1. **Use GPU**: Processing is significantly faster with GPU support
2. **Image size**: Smaller images process faster; consider resizing large images
3. **Mode selection**: Use Low mode for testing, High mode for final images

## Credits

- **Fawkes**: Developed by [Shawn Shan](https://github.com/Shawn-Shan) and the SANDLab at University of Chicago
- **Original Paper**: [Fawkes: Protecting Privacy against Unauthorized Deep Face Recognition](https://www.shawnshan.com/files/publication/fawkes.pdf)

## License

This web interface is provided as-is. Please refer to the [original Fawkes repository](https://github.com/Shawn-Shan/fawkes) for licensing information regarding the Fawkes algorithm and implementation.

## Disclaimer

This tool is intended for privacy protection and educational purposes. Users are responsible for ensuring their use complies with applicable laws and regulations. The effectiveness of Fawkes may vary depending on the facial recognition system being protected against.
