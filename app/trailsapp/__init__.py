import yaml
import requests
from flask import Flask, jsonify, request, render_template, redirect, make_response, url_for, flash
from urllib.parse import urlencode
import os
import io
import gpxpy
import trailsapp.analyze as analyze
import logging


import requests_cache

import time
import bravado
import bravado.client
import bravado.requests_client
import bravado.http_client
from bravado.requests_client import RequestsClient
from bravado.client import SwaggerClient

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

requests_cache.install_cache('appcache')

app = Flask(__name__, template_folder="/templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY").encode()

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

def get_request_token():
    token = request.cookies.get('strava_token', None)
    if token is None:
        logger.warning("no token")
        raise UnauthorizedError()

    return token
    
def get_athlete(token=None):
    if token is None:
        token = get_request_token()
    return requests.get("https://www.strava.com/api/v3/athlete", headers={"Authorization": f"Bearer {token}"}).json()

def get_swagger(token=None):
    if token is None:
        token = get_request_token()

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
    try:
        return yaml.safe_load(open("strava-client.yaml"))
    except IOError:
        return yaml.safe_load(open("/strava-client.yaml"))


#@app.errorhandler(Exception)
#def error(exception):
#    return make_response("error")

class UnauthorizedError(Exception):
    pass

@app.errorhandler(UnauthorizedError)
def unauthorized(exception):
    return redirect(url_for("auth"))

@app.route("/")
def root():
    return redirect(url_for("routes"))
    
def fetch_activity_streams(activity):
    client = get_swagger()

    activity['streams'] = client.Streams.getActivityStreams(
        id=activity['id'], 
        keys="time, distance, latlng, altitude, velocity_smooth, heartrate, cadence, watts, temp, moving, grade_smooth".split(", "),
        key_by_type=True,
        ).response().result


    print(activity['name'])

def fetch_route_gpx(route):
    print("getting route gpx for", route['id'])
    route['route_gpx'] = gpxpy.parse(io.BytesIO(requests.get(f"https://www.strava.com/api/v3//routes/{route['id']}/export_gpx", 
        params=dict(
            per_page=100
            ),
        headers={'Authorization': 'Bearer '+get_request_token()}
        ).content))
    route['route_points'] = route['route_gpx'].tracks[0].segments[0].points

    print("got", route['route_gpx'].tracks[0])

@app.route("/routes")
def routes():
    token = get_request_token()

    athlete = get_athlete()

    routes = [r for r in requests.get(f"https://www.strava.com/api/v3/athletes/{athlete['id']}/routes", 
            params=dict(
                per_page=200
                ),
            headers={'Authorization': 'Bearer '+token}
            ).json() if r['type'] != 1]

    for route in routes:
        if not analyze.analyze_route(route, onlycache=True):
            fetch_route_gpx(route)
        analyze.analyze_route(route)

    return render_template("routes.html", user_name=athlete['firstname'], routes=routes)

@app.route("/activities")
def activities():
    token = get_request_token()

    athlete = get_athlete()

    activities = []

    page = 1
    per_page = 100
    nmax = 150
    while True:
        _ = requests.get("https://www.strava.com/api/v3/athlete/activities", 
                params=dict(
                    per_page=per_page,
                    page=page,
                    ),
                headers={'Authorization': 'Bearer '+token}
                ).json()

        if not isinstance(_, list):
            print(_)
            break

        print("got page", page, "n", len(_), "total", len(activities))
        if len(_) == 0:
            break
        activities += _
        page += 1

        if len(activities)>nmax:
            break

    activities = [ activity for activity in activities if activity['type'] != "Ride" ]

    for activity in activities:
        fetch_activity_streams(activity)
        analyze.analyze_activity(activity, analyze.load_model("v0"))

    return render_template("activities.html", user_name=athlete['firstname'], activities=activities)

def get_auth_url():
    return "http://www.strava.com/oauth/authorize?" + urlencode(dict(
                client_id=read_conf()['client_id'],
                response_type="code",
                redirect_uri=os.environ.get("OAUTH_REDIRECT", "https://trail.app.volodymyrsavchenko.com/exchange_token"),
                approval_prompt="force",
                scope="activity:read",
                #scope="activity:read_all",
          ))
 
@app.route("/auth")
def auth():
    return render_template("index.html", auth_url=get_auth_url())

@app.route("/exchange_token")
def exchange_token():
    code = request.args.get("code")

    conf = read_conf()
        
    logger.warning("requested to exchange token")
    
    r=requests.post("https://www.strava.com/api/v3/oauth/token",
              data=dict(
                        client_id=conf['client_id'],
                        client_secret=conf['client_secret'],
                        code=code,
                        grant_type="authorization_code",
                   )
              )

    if r.status_code != 200:
        logger.warning("oauth did not return: %s", r.text)
        return redirect(url_for("root"))

    token=r.json()['access_token']

    athlete = get_athlete(token=token)

    logger.info("found athelete", athlete)

    if athlete['id'] not in [31879825,]:
        logger.warning(f"Sorry {athlete['firstname']} {athlete['id']}, not allowed in")
        flash("Sorry {athlete['firstname']}, we can not let you in here")
        return redirect(url_for("root"))

    r = redirect(url_for("root"))
    r.set_cookie('strava_token', token, max_age=60*60)

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


@app.route("/clear-cache")
def clear_cache():
    requests_cache.clear()
    flash("cache cleared!")
    return redirect(url_for("root"))

@app.route("/logout")
def logout():
    r = redirect(url_for("root"))
    r.delete_cookie('strava_token')
    return r
