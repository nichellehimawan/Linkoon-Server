import requests

url_base = "https://linkoon-6293f-default-rtdb.asia-southeast1.firebasedatabase.app"

def get_link(file, item="", info="", index=""):
    url = f"{url_base}/{file}{item}{info}{index}.json"
    return url

def read(file):
    url = get_link(file)
    response = requests.get(url)
    data = response.json()
    return data

def add(file, data):
    url = get_link(file)
    requests.post(url, json=data)

def add_keyed(file, item, info, index, data):
    url = get_link(file, item, info, index)
    requests.put(url, json=data)

def delete(file, key):
    url = get_link(file, f"/{key}")
    requests.delete(url)