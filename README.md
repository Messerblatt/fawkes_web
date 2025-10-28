# Fawkes Web Interface

A modern web application for [Fawkes](https://github.com/Shawn-Shan/fawkes), the privacy-preserving tool that protects images against facial recognition systems.

## Overview

Fawkes Web Interface provides an easy-to-use graphical interface for the Fawkes image cloaking system. Upload your images through a simple drag-and-drop interface and apply privacy-preserving modifications to protect against unauthorized facial recognition.

## Features

- **Modern UI**: Clean, minimal design with drag-and-drop image upload
- **Real-time Processing**: Live console output showing cloaking progress
- **Multiple Cloaking Modes**: Low, Mid, and High intensity options
- **GPU Detection**: Automatically detects GPU availability and adjusts available modes
- **Instant Download**: Download cloaked images immediately after processing
- **WebSocket Updates**: Real-time status updates during the cloaking process

## What is Fawkes?

Fawkes is a privacy tool that applies imperceptible modifications to images to protect them against unauthorized facial recognition systems. It "cloaks" faces in images, making them unrecognizable to facial recognition models while remaining visually unchanged to human observers.

## Prerequisites

- Python 3.7 or higher
- Node.js and npm (for the package.json dependencies listed, though the main app is Flask-based)
- TensorFlow 2.x
- The original [Fawkes repository](https://github.com/Shawn-Shan/fawkes) cloned into the `fawkes/` directory

## Installation

### 1. Clone this repository

\`\`\`bash
git clone <your-repo-url>
cd fawkes-web-app
\`\`\`

### 2. Install Python dependencies

\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 3. Set up Fawkes

Clone the original Fawkes repository into the project:

\`\`\`bash
git clone https://github.com/Shawn-Shan/fawkes.git
cd fawkes
pip install -e .
cd ..
\`\`\`

Ensure the following file structure:

\`\`\`
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
\`\`\`

### 4. Verify installation

Check that all components are properly installed:

\`\`\`bash
python -c "import tensorflow as tf; print(f'TensorFlow: {tf.__version__}')"
python -c "from flask_socketio import SocketIO; print('Flask-SocketIO: OK')"
\`\`\`

## Usage

### Starting the server

Run the Flask application:

\`\`\`bash
python app.py
\`\`\`

Or use the provided run script:

\`\`\`bash
python run_server.py
\`\`\`

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

## File Structure

\`\`\`
fawkes-web-app/
├── app.py                 # Main Flask application
├── run_server.py         # Server startup script
├── requirements.txt      # Python dependencies
├── package.json          # Node.js dependencies (for reference)
├── templates/
│   └── index.html       # Web interface
├── fawkes/              # Fawkes library (clone from GitHub)
│   ├── protection.py    # Main cloaking script
│   └── ...
├── images/              # Upload directory (auto-created)
└── scripts/
    └── setup.py         # Setup helper script
\`\`\`

## Output Files

Cloaked images are saved in the `images/` directory with the following naming convention:

\`\`\`
original_filename.jpg → original_filename_cloaked.png
\`\`\`

All cloaked images are converted to PNG format to preserve quality.

## Troubleshooting

### "Fawkes directory not found"
Ensure the Fawkes repository is cloned into the `fawkes/` directory at the project root.

### "protection.py not found"
Verify that `fawkes/protection.py` exists and is accessible.

### GPU not detected
Check your TensorFlow installation:
\`\`\`bash
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
\`\`\`

### Port already in use
Change the port in `app.py`:
\`\`\`python
socketio.run(app, debug=True, host='0.0.0.0', port=5001)  # Change 5000 to another port
\`\`\`

### Processing fails
Check the console output for detailed error messages. Common issues:
- Insufficient memory
- Invalid image format
- Missing dependencies

## Deployment

### Production deployment

For production use, disable debug mode and use a production WSGI server:

\`\`\`bash
pip install gunicorn
gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:5000
\`\`\`

### Using systemd (Linux)

Edit the provided `file-server.service` file:

\`\`\`ini
[Service]
WorkingDirectory=/path/to/fawkes-web
ExecStart=/usr/bin/python3 run_server.py
\`\`\`

Then enable and start:

\`\`\`bash
sudo cp file-server.service /etc/systemd/system/fawkes-web.service
sudo systemctl enable fawkes-web
sudo systemctl start fawkes-web
\`\`\`

## Security Considerations

- The application clears the `images/` directory before each upload
- Uploaded images are processed server-side and should be deleted after use
- For production deployment, implement proper authentication and rate limiting
- Consider using HTTPS for all connections

## Performance Tips

1. **Use GPU**: Processing is significantly faster with GPU support
2. **Image size**: Smaller images process faster; consider resizing large images
3. **Mode selection**: Use Low mode for testing, High mode for final images
4. **Batch processing**: For multiple images, process them sequentially

## Contributing

Contributions are welcome! Please ensure:
- Code follows the existing style
- All features are tested
- Documentation is updated

## Credits

- **Fawkes**: Developed by [Shawn Shan](https://github.com/Shawn-Shan) and the SANDLab at University of Chicago
- **Original Paper**: [Fawkes: Protecting Privacy against Unauthorized Deep Face Recognition](https://www.shawnshan.com/files/publication/fawkes.pdf)

## License

This web interface is provided as-is. Please refer to the [original Fawkes repository](https://github.com/Shawn-Shan/fawkes) for licensing information regarding the Fawkes algorithm and implementation.

## Support

For issues related to:
- **Web interface**: Open an issue in this repository
- **Fawkes algorithm**: Refer to the [original Fawkes repository](https://github.com/Shawn-Shan/fawkes)

## Disclaimer

This tool is intended for privacy protection and educational purposes. Users are responsible for ensuring their use complies with applicable laws and regulations. The effectiveness of Fawkes may vary depending on the facial recognition system being protected against.
