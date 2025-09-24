from flask import Flask, request, jsonify
import json
import requests
import firebase_controls as fb
import re
import math

app = Flask(__name__)

GMAPS_API_KEY = "AIzaSyCDeWKmcsH2TWVtaa2yFx02kGeQz-h6jVo"

def expand_link(link):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    session = requests.Session()
    resp = session.get(link, headers=headers, allow_redirects=True, timeout=10)
    return resp.url

def linktocoords(link):
    try:
        url = expand_link(link)

        if '@' in url:
            after_at = url.split('@')[1]
            coords = after_at.split('/')[0]
            lat, lon = coords.split(',')[0:2]
            return float(lat), float(lon)

        match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url)
        lat, lon = match.groups()
        return float(lat), float(lon)
    except (IndexError, ValueError):
        print("could not get coordinates")
        return None
    
def distance_matrix(lat1, lon1, lat2, lon2):
    api = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": f"{lat1},{lon1}", "destinations": f"{lat2},{lon2}", "key": GMAPS_API_KEY}
    resp = requests.get(api, params=params).json()
    try:
        element = resp['rows'][0]['elements'][0]
        if element['status'] == "OK":
            return element['distance']['value'] / 1000
        else:
            print("Distance Matrix Status: ", element['status'])
            return None
    except Exception as e:
        print("Error in parsing Distance Matrix: ", e)
        return None
    
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def get_distance(lat1, lon1, lat2, lon2):
    distance_km = distance_matrix(lat1, lon1, lat2, lon2)
    if distance_km is not None:
        return distance_km
    distance_km = haversine_distance(lat1, lon1, lat2, lon2)
    return distance_km

def dmatch(donor, donor_request, recipients):
    matches = []
    for recipient in recipients:
        available_items = {"type 1": 0, "type 2": 0, "type 3": 0}
        for index, need in enumerate(recipient["items"]):
            for donation in donor_request:
                if donation["type"] == need["type"]:
                    available_items[f"type {index+1}"] += int(donation["quantity"])
            if index == 0 or abs(available_items[f"type {index+1}"] - int(need["quantity"])) > maxdiff:
                maxdiff = abs(available_items[f"type {index+1}"] - int(need["quantity"]))
        if len(matches) == 0 or maxdiff < matches[0]["maxdiff"]:
            dlat, dlon = linktocoords(donor["gmaps"])
            for user in fb.read("recipients").values():
                if user["username"] == recipient["user"]:
                    rlat, rlon = linktocoords(user["gmaps"])
                    break
            distance = get_distance(dlat, dlon, rlat, rlon)
            new_match = {"donor": donor["username"], 
                         "recipient": recipient["user"], 
                         "items": donor_request, 
                         "dcoords": {0: dlat, 1: dlon}, 
                         "rcoords": {0: rlat, 1: rlon}, 
                         "distance": distance, 
                         "maxdiff": maxdiff}
            matches.insert(0, new_match)
        if len(matches) == 4:
            matches = matches[:3]
            for match in matches:
                del match["maxdiff"]
            return matches
    for match in matches:
        del match["maxdiff"]
    return matches

def rmatch(recipient, recipient_request, donors):
    matches = []
    for donor in donors:
        available_items = {"type 1": 0, "type 2": 0, "type 3": 0}
        for index, need in enumerate(recipient_request):
            for donation in donor["items"]:
                if donation["type"] == need["type"]:
                    available_items[f"type {index+1}"] += int(donation["quantity"])
            if index == 0 or abs(available_items[f"type {index+1}"] - int(need["quantity"])) > maxdiff:
                maxdiff = abs(available_items[f"type {index+1}"] - int(need["quantity"]))
        if len(matches) == 0 or maxdiff < matches[0]["maxdiff"]:
            rlat, rlon = linktocoords(recipient["gmaps"])
            dlat, dlon = linktocoords(donor["gmaps"])
            distance = get_distance(dlat, dlon, rlat, rlon)
            new_match = {"donor": donor["user"], 
                         "recipient": recipient["username"], 
                         "items": donor["items"], 
                         "dcoords": {0: dlat, 1: dlon}, 
                         "rcoords": {0: rlat, 1: rlon}, 
                         "distance": distance, 
                         "maxdiff": maxdiff}
            matches.insert(0, new_match)
        if len(matches) == 4:
            matches = matches[:3]
            for match in matches:
                del match["maxdiff"]
            return matches
    for match in matches:
        del match["maxdiff"]
    return matches

@app.route('/match_donor', methods=['POST'])
def match_donor():
    try:
        donor = request.json
        donors = fb.read('donorrequestdelivery')
        for req in donors.values():
            if req["user"] == donor["username"]:
                donor_request = req["items"]
                break
        recipients = list(fb.read('recipientrequestdelivery').values())
        new_matches = dmatch(donor, donor_request, recipients)
        for match in new_matches:
            fb.add("matches", match)
        return "ok"
    except AttributeError:
        return "ok"

@app.route('/match_recipient', methods=['POST'])
def match_recipient():
    try:
        recipient = request.json
        recipients = fb.read('recipientrequestdelivery')
        for req in recipients.values():
            if req["user"] == recipient["username"]:
                recipient_request = req["items"]
                break
        donors = list(fb.read('donorrequestdelivery').values())
        new_matches = rmatch(recipient, recipient_request, donors)
        for match in new_matches:
            fb.add("matches", match)
        return "ok"
    except AttributeError:
        return "ok"

if __name__ == '__main__':
    app.run(debug=True)