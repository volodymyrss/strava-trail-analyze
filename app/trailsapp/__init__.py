import glob
import json
import yaml
import requests
from flask import Flask, jsonify, request, render_template, redirect, make_response, url_for, flash, send_file
from werkzeug.utils import secure_filename
from urllib.parse import urlencode
import os
import io
import gpxpy
import trailsapp.analyze as analyze
import trailsapp.solid as solid
import logging


import requests_cache
import diskcache as dc

import time
import hashlib
import bravado.client
import bravado.requests_client
import bravado.http_client
from bravado.requests_client import RequestsClient
from bravado.client import SwaggerClient

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

requests_cache.install_cache('appcache')

app = Flask(__name__, 
            template_folder=os.environ.get("FLASK_TEMPLATES", "/templates"),
            # static_folder=os.environ.get("FLASK_STATIC", "/static")
            )
app.secret_key = os.environ.get("FLASK_SECRET_KEY").encode()

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

app.register_blueprint(solid.solid_app)

athlete_cache = dc.Cache('athlete-cache')
athlete_activity_cache = dc.Cache('athlete-activity-cache')


class RateLimitError(Exception):
    pass


def get_access_token():
    token = request.cookies.get('oauth2_token', None)
    if token is None:
        logger.warning("no token")
        raise UnauthorizedError()
    
    print("token", token)

    return token

    
def get_athlete(token=None):
    if token is None:
        token = get_access_token()

    print("get_athlete token", token)

    tokenhash = hashlib.md5(token.encode()).hexdigest()[:8]
    if tokenhash in athlete_cache:
        return athlete_cache[tokenhash]

    with requests_cache.disabled():
        r = requests.get("https://gitlab.com/oauth/userinfo", headers={"Authorization": f"Bearer {token}"})
        # r = requests.get("https://gitlab.com/oauth/introspect", headers={"Authorization": f"Bearer {token}"})
        print(r, r.content)

    athlete_id = r.json()['sub']

    if athlete_id not in ['1340065']:
        raise UnauthorizedError()

    athlete_cache[tokenhash] = r.json()

    if r.status_code == 429:
        raise RateLimitError()

    if r.status_code != 200:
        raise RuntimeError(f"{r}: {r.text}")

    return r.json()

def get_swagger(token=None):
    if token is None:
        token = get_access_token()

    http_client = RequestsClient()
    http_client.set_api_key(
                'www.strava.com', 'Bearer '+token,
                    param_name='Authorization', param_in='header'
                    )

    client = SwaggerClient.from_url(
                'https://developers.strava.com/swagger/swagger.json',
                    http_client=http_client,
                        config={
                                    'validate_swagger_spec': False,
                                    'validate_responses': False,
                                    'validate_requests': False,
                        },
                    )
    athlete = client.Athletes.getLoggedInAthlete().response().result
    athlete

    return client

def read_conf():
    config = yaml.safe_load(open(os.getenv("TRAIL_APP_CONFIG", "config.yaml")))
    print(config)
    config['client'] = yaml.safe_load(open("client.yaml"))
    return config


#@app.errorhandler(Exception)
#def error(exception):
#    return make_response("error")

class UnauthorizedError(Exception):
    pass

@app.errorhandler(UnauthorizedError)
def unauthorized(exception):
    return redirect(url_for("auth"))

@app.errorhandler(RateLimitError)
def unauthorized(exception):
    return make_response("Rate limit exceeded while querying strava! Please retry later.")


@app.route("/")
def root():
    return redirect(url_for("routes"))


@app.route("/routes")
def routes():
    athlete = get_athlete()

    print("athlete", athlete)
    
    config = read_conf() 

    athlete_dir = os.path.join(config['data_dir'], athlete['sub'])
    routes = []

    messages = []
    if message := request.args.get("message", None):
        messages.append(message)
    
    for route in glob.glob(f"{athlete_dir}/*.json"):
        with open(route, "r") as f:
            routes.append(json.load(f))

    return render_template("routes.html", user_name=athlete['name'], routes=routes, messages=messages)


def get_auth_url():
    conf = read_conf()
    return "https://gitlab.com/oauth/authorize?" + urlencode(dict(
                client_id=conf['client']['client_id'],
                response_type="code",
                redirect_uri=conf['client']["redirect_base"] + "/exchange_token",
                # approval_prompt="force",
                scope="read_user openid profile email",
          ))
 
@app.route("/auth")
def auth():
    return render_template("index.html", auth_url=get_auth_url())

@app.route("/exchange_token")
def exchange_token():
    code = request.args.get("code")
    conf = read_conf()
        
    logger.warning("requested to exchange token")
    
    r = requests.post("https://gitlab.com/oauth/token",
              data=dict(
                        client_id=conf['client']['client_id'],
                        client_secret=conf['client']['client_secret'],
                        code=code,
                        grant_type="authorization_code",
                        redirect_uri=conf['client']["redirect_base"] + "/exchange_token",
                   )
              )

    if r.status_code != 200:
        logger.warning("oauth did not return: %s", r.text)
        return redirect(url_for("root"))


    token=r.json()['access_token']

    athlete = get_athlete(token=token)

    logger.info("found athlete: %s", str(athlete))

    r = redirect(url_for("root"))
    r.set_cookie('oauth2_token', token, max_age=60*60)

    return r

@app.route('/images/bar/<fractions>')
def get_image(fractions):
    image_binary = analyze.pngbar(list(map(float, fractions.split(","))))
    response = make_response(image_binary)
    response.headers.set('Content-Type', 'image/png')
 #   response.headers.set(
 #       'Content-Disposition', 'attachment', filename='some.png' 
 #   )
    return response


@app.route("/recompute")
def clear_cache():
    # requests_cache.clear()
    # athlete_activity_cache.clear()
    # athlete_cache.clear()

    config = read_conf()

    athlete = get_athlete()
    athlete_dir = os.path.join(config['data_dir'], athlete['sub'])

    for gpxfn in glob.glob(f"{athlete_dir}/*.gpx"):        
        gpx_to_entry(gpxfn)
    
    flash("cache cleared!")    
    return redirect(url_for("root"))

@app.route("/logout")
def logout():
    r = redirect(url_for("root"))
    r.delete_cookie('oauth2_token')
    return r


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    config = read_conf()
    athlete = get_athlete()

    if request.method == 'POST':
        print("post file upload")

        print("request.files", request.files)
        
        if 'file' not in request.files:
            print("no file part")
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']

        athlete_dir = os.path.join(config['data_dir'], athlete['sub'])
        os.makedirs(athlete_dir, exist_ok=True)
        
        if file.filename == '':
            print("no selected file")
            flash('No selected file')
            return redirect(request.url)
        
        if not file.filename.endswith(".gpx") and not file.filename.endswith(".GPX"):
            print("invalid file type")
            flash('Invalid file type')
            return redirect(request.url)
        
        if file:
            print("saving file")
            filename = secure_filename(file.filename)
            fullfn = os.path.join(athlete_dir, filename)
            file.save(fullfn)
            
            entry = gpx_to_entry(fullfn)

            return redirect(url_for('routes', message=f"file {entry['name']} uploaded and analysed: {entry}!"))
    
        print("problem uploading file", file)
        return redirect(url_for('routes', message="problem uploading file!"))
        
    return f'''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File, {athlete['name']}</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''


def gpx_to_entry(fullfn):
    gpx = gpxpy.parse(open(fullfn).read())
            
    print("gpx", gpx)

    track = list(gpx.tracks)[0]
    segment = list(track.segments)[0]

    print("segment", segment)

    entry = {
        "name": gpx.name,
        "route_points": segment.points,
        "route_gpx": gpx,
        "type": "gpx",
        "sub_type": "gpx",
    }    

    entry['analysis'] =  analyze.analyze_route(entry)

    del entry['route_gpx']
    del entry['route_points']

    with open(fullfn + ".json", "w") as f:
        json.dump(entry, f, indent=4, sort_keys=True)

    return entry
