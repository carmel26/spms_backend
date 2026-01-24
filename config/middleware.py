"""
Custom CORS middleware for handling preflight OPTIONS requests
"""

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin


class CustomCorsMiddleware(MiddlewareMixin):
    """
    Middleware to handle CORS preflight OPTIONS requests
    This ensures OPTIONS requests get proper CORS headers even if they're denied by permission classes
    """
    
    def process_request(self, request):
        """Handle OPTIONS preflight requests"""
        if request.method == 'OPTIONS':
            return self.preflight_response(request)
        return None
    
    def preflight_response(self, request):
        """
        Send CORS headers for preflight OPTIONS requests
        """
        response = HttpResponse()
        
        # Get the origin from the request
        origin = request.META.get('HTTP_ORIGIN', '')
        
        # Import settings to check if origin is allowed
        from django.conf import settings
        
        # Check if origin is in allowed origins
        allowed = False
        if origin in settings.CORS_ALLOWED_ORIGINS:
            allowed = True
        elif settings.DEBUG and 'localhost' in origin:
            allowed = True
        elif settings.DEBUG and '127.0.0.1' in origin:
            allowed = True
        elif settings.DEBUG and '10.10.14.94' in origin:
            allowed = True
        
        if allowed:
            # Set CORS headers
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'DELETE, GET, OPTIONS, PATCH, POST, PUT'
            response['Access-Control-Allow-Headers'] = 'accept, accept-encoding, authorization, content-type, dnt, origin, user-agent, x-csrftoken, x-requested-with'
            response['Access-Control-Max-Age'] = '3600'
            response['Access-Control-Allow-Credentials'] = 'true'
        
        response.status_code = 200
        return response
