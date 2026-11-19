FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && torch_dir="$(python -c 'import pathlib, torch; print(pathlib.Path(torch.__file__).parent)')" \
    && rm -rf "$torch_dir/include" "$torch_dir/test"
RUN pip install --constraint requirements.txt numpy faiss-cpu
RUN pip install --constraint requirements.txt sentence-transformers
RUN pip install --constraint requirements.txt pymongo voyageai reportlab docker python-dotenv

COPY lab17_1_rag.py lab17_2_benchmark.py generate_pdf.py vector_index_definitions.json ./

CMD ["python", "lab17_1_rag.py"]
