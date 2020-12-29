FROM python:3.8
ADD requirements.txt /requirements.txt
RUN pip install -r requirements.txt

ADD app /app
RUN pip install /app
ADD app/templates /templates


RUN useradd app -u 1000 

WORKDIR /home/app

RUN chown app:app /home/app
RUN touch /strava-client.yaml

# default model
ADD lut_merged.npy /home/app/lut_merged.npy

USER app

ENTRYPOINT gunicorn trailsapp:app -b 0.0.0.0:8000 -w 8 --log-level debug
