from http.server import BaseHTTPRequestHandler
import json

# Define a request handler class
class MyRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Simple GET request handler
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Hello, world!')

# Lambda entry point
def lambda_handler(event, context):
    # Create a mock request handler for AWS Lambda
    class MockRequestHandler:
        def send_response(self, code):
            pass
        def send_header(self, keyword, value):
            pass
        def end_headers(self):
            pass
        def wfile(self):
            return self

    handler = MockRequestHandler()
    
    # Ensure `handler` is a class and check if it's a subclass of BaseHTTPRequestHandler
    if not isinstance(handler, type) or not issubclass(handler, BaseHTTPRequestHandler):
        raise TypeError("Handler must be a subclass of BaseHTTPRequestHandler")

    # Process the request and generate a response
    try:
        request = {
            'httpMethod': event.get('httpMethod', 'GET'),
            'path': event.get('path', '/'),
            'headers': event.get('headers', {}),
            'body': event.get('body', '')
        }

        # Simulate processing and return response
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Hello, world!'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
