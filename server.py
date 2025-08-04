from flask import Flask, request, jsonify
import json
import requests
import firebase_controls as fb

app = Flask(__name__)

GMAPS_API_KEY = "AIzaSyCDeWKmcsH2TWVtaa2yFx02kGeQz-h6jVo"

def linktocoords(link):
    resp = requests.get(link, allow_redirects=True)
    url = resp.url
    after_at = url.split('@')[1]
    coords = after_at.split('/')[0]
    lat, lon = coords.split(',')[0:2]
    return float(lat), float(lon)

def get_distance(lat1, lon1, lat2, lon2):
    api = "https://maps.googleapis.com/maps/api/directions/json"
    params = {"origin": f"{lat1},{lon1}", "destination": f"{lat2},{lon2}", "key": GMAPS_API_KEY}
    resp = requests.get(api, params=params).json()
    distance_km = resp['routes'][0]['legs'][0]['distance']['value'] / 1000
    return distance_km

def dmatch(donor, donor_request, recipients):
    matches = []
    for recipient in recipients:
        available_items = {"type 1": 0, "type 2": 0, "type 3": 0, "type 4": 0, "type 5": 0, "type 6": 0, "type 7": 0, "type 8": 0, "type 9": 0, "type 10": 0}
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
        available_items = {"type 1": 0, "type 2": 0, "type 3": 0, "type 4": 0, "type 5": 0, "type 6": 0, "type 7": 0, "type 8": 0, "type 9": 0, "type 10": 0}
        for index, need in enumerate(recipient_request):
            for donation in donor["items"]:
                if donation["type"] == need["type"]:
                    available_items[f"type {index+1}"] += int(donation["quantity"])
            if index == 0 or abs(available_items[f"type {index+1}"] - int(need["quantity"])) > maxdiff:
                maxdiff = abs(available_items[f"type {index+1}"] - int(need["quantity"]))
        if len(matches) == 0 or maxdiff < matches[0]["maxdiff"]:
            rlat, rlon = linktocoords(recipient["gmaps"])
            for user in fb.read("donors").values():
                if user["username"] == donor["user"]:
                    dlat, dlon = linktocoords(user["gmaps"])
                    break
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
        pass

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
        pass

if __name__ == '__main__':
    app.run(debug=True)