"""
Middleware for audit logging
"""
import json
from django.utils.deprecation import MiddlewareMixin
from apps.users.models import AuditLog


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log all API requests and responses
    for comprehensive audit trail
    """
    
    # Paths to exclude from audit logging
    EXCLUDED_PATHS = [
        '/static/',
        '/media/',
        '/favicon.ico',
        '/api/notifications/notifications/unread_count/',  # Too frequent
    ]
    
    # Methods to log
    LOGGED_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    
    def process_request(self, request):
        """Store request start time"""
        # Skip excluded paths
        for excluded in self.EXCLUDED_PATHS:
            if request.path.startswith(excluded):
                return None
        
        # Store request data for later use in process_response
        request._audit_log_data = {
            'path': request.path,
            'method': request.method,
            'ip_address': self.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
        }
        
        return None
    
    def process_response(self, request, response):
        """Log the request/response after processing"""
        # Skip if no audit data (excluded paths)
        if not hasattr(request, '_audit_log_data'):
            return response
        
        # Only log certain methods or failed requests
        if request.method not in self.LOGGED_METHODS and response.status_code < 400:
            return response
        
        try:
            # Extract action from method
            action_map = {
                'POST': 'CREATE',
                'PUT': 'UPDATE',
                'PATCH': 'UPDATE',
                'DELETE': 'DELETE',
                'GET': 'VIEW',
            }
            action = action_map.get(request.method, 'UNKNOWN')
            
            # Determine model and object from path
            model_name, object_id = self.parse_path(request.path)
            
            # Get user
            user = request.user if request.user.is_authenticated else None
            
            # Determine success
            success = 200 <= response.status_code < 400
            
            # Get error message if failed
            error_message = ''
            if not success:
                try:
                    error_data = json.loads(response.content.decode('utf-8'))
                    error_message = str(error_data)[:1000]
                except:
                    error_message = f"HTTP {response.status_code}"
            
            # Create description
            description = f"{request.method} {request.path}"
            
            # Create audit log
            AuditLog.objects.create(
                user=user,
                action=action,
                model_name=model_name,
                object_id=object_id,
                object_repr=f"{model_name} #{object_id}" if object_id else model_name,
                description=description,
                ip_address=request._audit_log_data['ip_address'],
                user_agent=request._audit_log_data['user_agent'],
                request_path=request._audit_log_data['path'],
                request_method=request._audit_log_data['method'],
                success=success,
                error_message=error_message
            )
        
        except Exception as e:
            # Don't let audit logging break the request
            print(f"Audit logging error: {e}")
        
        return response
    
    @staticmethod
    def get_client_ip(request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def parse_path(path):
        """Parse API path to extract model name and object ID"""
        # Example: /api/users/users/123/ -> (CustomUser, 123)
        # Example: /api/presentations/presentations/ -> (PresentationRequest, '')
        
        parts = [p for p in path.split('/') if p]
        
        if len(parts) < 2:
            return ('Unknown', '')
        
        # Map API paths to model names
        model_map = {
            'users': 'CustomUser',
            'groups': 'UserGroup',
            'presentations': 'PresentationRequest',
            'assignments': 'PresentationAssignment',
            'examiners': 'ExaminerAssignment',
            'supervisors': 'SupervisorAssignment',
            'notifications': 'Notification',
            'schools': 'School',
            'programmes': 'Programme',
            'reports': 'Report',
        }
        
        # Get model name from path
        if len(parts) >= 3:
            model_key = parts[2]  # e.g., 'users' from /api/users/users/
            model_name = model_map.get(model_key, model_key.capitalize())
        else:
            model_name = 'Unknown'
        
        # Get object ID if present
        object_id = ''
        if len(parts) >= 4 and parts[3].isdigit():
            object_id = parts[3]
        
        return (model_name, object_id)
