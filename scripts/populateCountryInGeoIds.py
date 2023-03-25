import requests

# For run this Script python populateCountryInGeoIds.py
response = requests.post('http://localhost:5000/populate-country-in-geo-ids')
if response.status_code == 200:
    print('Countries updated successfully')
else:
    print('Failed to update countries')
