FROM python:3.8
ADD requirements.txt /requirements.txt
RUN pip install -r requirements.txt

ENTRYPOINT gunicorn app:app -b 0.0.0.0:8000 --log-level debug
