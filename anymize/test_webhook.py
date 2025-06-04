#!/usr/bin/env python3

import requests
import urllib.request
import json
import sys
import time
from config_shared import N8N_WEBHOOK_URL

def test_webhook_with_requests():
    """Test the webhook using the requests library"""
    webhook_url = N8N_WEBHOOK_URL
    payload = {
        'id': '123456',
        'text': 'This is a test message from the webhook diagnostic script.'
    }
    
    print(f"\nAttempting to call webhook with requests: {webhook_url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = requests.post(
            webhook_url, 
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"Response status code: {response.status_code}")
        print(f"Response body: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Error with requests: {str(e)}")
        return False

def test_webhook_with_urllib():
    """Test the webhook using urllib (different HTTP client)"""
    webhook_url = N8N_WEBHOOK_URL
    payload = {
        'id': '123456',
        'text': 'This is a test message from the webhook diagnostic script using urllib.'
    }
    
    print(f"\nAttempting to call webhook with urllib: {webhook_url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        data = json.dumps(payload).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Anymize-Test/1.0'
        }
        
        req = urllib.request.Request(
            webhook_url,
            data=data, 
            headers=headers, 
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            body = response.read().decode('utf-8')
            
            print(f"Response status code: {status_code}")
            print(f"Response body: {body}")
            
            return status_code == 200
    except Exception as e:
        print(f"Error with urllib: {str(e)}")
        return False

def test_with_curl():
    """Generate curl command that can be run manually"""
    webhook_url = N8N_WEBHOOK_URL
    payload = {
        'id': '123456',
        'text': 'This is a test message from curl.'
    }
    
    curl_command = f'''
    curl -X POST \
    -H "Content-Type: application/json" \
    -d '{json.dumps(payload)}' \
    {webhook_url}
    '''
    
    print("\nYou can also try the following curl command manually:")
    print(curl_command)

if __name__ == "__main__":
    print("\n===== WEBHOOK DIAGNOSTIC TOOL =====\n")
    print("Testing connection to anonymization webhook...")
    
    # Test with requests
    requests_success = test_webhook_with_requests()
    
    # Wait a bit to avoid rate limiting
    time.sleep(2)
    
    # Test with urllib
    urllib_success = test_webhook_with_urllib()
    
    # Generate curl command
    test_with_curl()
    
    print("\n===== RESULTS =====\n")
    print(f"Requests library test: {'SUCCESS' if requests_success else 'FAILED'}")
    print(f"Urllib library test: {'SUCCESS' if urllib_success else 'FAILED'}")
    
    if not (requests_success or urllib_success):
        print("\nAll webhook tests failed. This could indicate:")
        print("1. The webhook URL is incorrect")
        print("2. There is a network connectivity issue")
        print("3. The webhook server is down or not accepting connections")
        print("4. The payload format is not what the webhook expects")
        
        sys.exit(1)
    else:
        print("\nAt least one test succeeded! The webhook is reachable.")
        sys.exit(0)
