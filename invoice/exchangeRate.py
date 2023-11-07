import requests

def get_exchange_rate(fromCurr, toCurr):
    with open('APIKEY.txt', 'r') as f:
        api_key = f.read().strip()

    url = 'https://v6.exchangerate-api.com/v6/' + api_key + '/latest/'

    response = requests.get(url + fromCurr)
    if response.status_code != 200:
        raise Exception('ERROR: API request unsuccessful.')
    data = response.json()
    rate = round(data['conversion_rates'][toCurr], 2)
    return str(rate)
