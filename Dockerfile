FROM python:3.8
ADD requirements.txt /requirements.txt
RUN pip install -r requirements.txt

ADD app /app
RUN pip install /app
ADD app/templates /templates

# default model
ADD lut_merged.npy /lut_merged.npy

RUN useradd app -u 1000 

WORKDIR /home/app

RUN chown app:app /home/app
RUN touch /strava-client.yaml

USER app

ENTRYPOINT gunicorn trailsapp:app -b 0.0.0.0:8000 -w 8 --log-level debug
