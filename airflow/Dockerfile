FROM apache/airflow:2.10.5-python3.10

# Install your project dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Install PyTorch with CUDA 12.8 support
RUN pip3 install --verbose torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128