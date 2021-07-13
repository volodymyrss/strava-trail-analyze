"""
This is a Flask application for Inrupt Solid profile viewer. 
 
"""
 
from flask import Flask, jsonify, render_template, request, Blueprint
import json
import logging
import requests
import rdflib   
from rdflib import URIRef,Graph,RDF
from rdflib.namespace import FOAF

logger=logging.getLogger(__name__)
 
def parse_graph_uri(G, uri):
    G.parse(
            data=requests.get(uri, 
                              headers={'Accept': 'application/rdf+xml'}).text, 
            format="xml", 
            publicID="https://vs.solidweb.org/",
          )
    return G
 
solid_app = Blueprint('solid_app', __name__)
 
def post_friends_list(uri):
    "create,parse graph and get the friends list for the given URI"
    # Create a Empty graph      
    graph = rdflib.Graph()   
    parse_graph_uri(graph, uri)
    for person in graph[: RDF.type: FOAF.Person]:
        name = graph.value(person, FOAF.name)             
        friends = list(graph[person:FOAF.knows])
        logger.info('%s friends', friends)
        if friends:
            logger.info("%s's friends:", graph.value(person, FOAF.name))           
 
        return friends,name          
 
 
@solid_app.route("/solid", methods=['GET','POST'])
@solid_app.route("/solid/view", methods=['GET','POST'])
def view():
    "Endpoint for getting the friends list for the given URI"
    if request.method == 'GET':
        #return the form
        return render_template('sample_solid.html')
    if request.method == 'POST':
        #return the answer
        uri = request.form.get('profile')        
        result,name = post_friends_list(uri)        
        api_response = {"answer": result, 
                        "name": name}        
        return jsonify(api_response)
 
