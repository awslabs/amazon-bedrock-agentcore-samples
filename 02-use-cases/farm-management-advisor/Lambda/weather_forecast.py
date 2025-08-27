# Lambda function code (Weather forecast)

import json
import requests

def lambda_handler(event, context):
    """AWS Lambda function to get weather forecast using weather.gov API"""
    
    location = event.get('location')
    if not location:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Location parameter required'})
        }
    
    try:
        # Check if location is a zip code (5 digits) or coordinates (lat,lon)
        if location.isdigit() and len(location) == 5:
            # Convert zip code to coordinates
            geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
            geo_response = requests.get(geocode_url, timeout=10)
            
            if geo_response.status_code != 200:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Could not geocode zip code'})
                }
            
            geo_data = geo_response.json()
            if not geo_data.get('results'):
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Zip code not found'})
                }
            
            lat = geo_data['results'][0]['latitude']
            lon = geo_data['results'][0]['longitude']
            location = f"{lat},{lon}"
        
        # Step 1: Get points data
        points_url = f"https://api.weather.gov/points/{location}"
        points_response = requests.get(points_url, timeout=10)
        
        if points_response.status_code != 200:
            return {
                'statusCode': points_response.status_code,
                'body': json.dumps({'error': 'Invalid location or weather.gov API error'})
            }
        
        points_data = points_response.json()
        forecast_url = points_data['properties']['forecast']
        
        # Step 2: Get forecast
        forecast_response = requests.get(forecast_url, timeout=10)
        
        if forecast_response.status_code != 200:
            return {
                'statusCode': forecast_response.status_code,
                'body': json.dumps({'error': 'Forecast API error'})
            }
        
        forecast_data = forecast_response.json()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'location': location,
                'forecast': forecast_data['properties']['periods']
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }