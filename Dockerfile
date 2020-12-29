FROM python:3.8
ADD requirements.txt /requirements.txt
RUN pip install -r requirements.txt

ADD trailsapp /trailsapp
RUN pip install /trailsapp

# default model
ADD lut_merged.npy /lut_merged.npy

ENTRYPOINT gunicorn trailsapp:app -b 0.0.0.0:80 --log-level debug
