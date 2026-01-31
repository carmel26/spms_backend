from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import School, Programme, PresentationType
from .serializers import SchoolSerializer, ProgrammeSerializer, PresentationTypeSerializer
from django.shortcuts import get_object_or_404
from apps.users.models import CustomUser
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


class SchoolViewSet(viewsets.ModelViewSet):
    """
    ViewSet for School CRUD operations
    """
    queryset = School.objects.all()
    serializer_class = SchoolSerializer

    def get_permissions(self):
        """Allow public access to list and retrieve, require auth for modifications"""
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = School.objects.all()
        # Filter by active status if requested
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset

    def create(self, request, *args, **kwargs):
        print("Received data:", request.data)  # Debug log
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("Validation errors:", serializer.errors)  # Debug log
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        """Ensure PATCH works with partial payloads like dean assignment."""
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def programme(self, request, pk=None):
        """Return school and programme information.

        The endpoint supports two behaviours for compatibility:
        - If `pk` matches a School id, return that school's name and a list of its programmes.
        - If `pk` matches a User id, return the user's linked school and programme names.
        """
        # Try to find a School first
        try:
            school = get_object_or_404(School, pk=pk)
            programmes = Programme.objects.filter(school=school)
            programme_name = programmes.first().name if programmes.exists() else None
            return Response({
                'school_name': school.name,
                'programme_name': programme_name
            })
        except Exception:
            # If no school found, try interpreting pk as a user id
            try:
                user = get_object_or_404(CustomUser, pk=pk)
                school = user.school
                programme = user.programme
                return Response({
                    'school_name': school.name if school else None,
                    'programme_name': programme.name if programme else None
                })
            except Exception:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class ProgrammeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Programme CRUD operations
    """
    queryset = Programme.objects.all()
    serializer_class = ProgrammeSerializer

    def get_permissions(self):
        """Allow public access to list and retrieve, require auth for modifications"""
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = Programme.objects.all()
        # Filter by school if requested
        school_id = self.request.query_params.get('school', None)
        if school_id is not None:
            queryset = queryset.filter(school_id=school_id)
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class PresentationTypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Presentation Type CRUD operations
    Admin can create/edit/delete presentation types for different programme levels
    """
    queryset = PresentationType.objects.all()
    serializer_class = PresentationTypeSerializer

    def get_permissions(self):
        """Allow public access to list and retrieve, require auth for modifications"""
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = PresentationType.objects.all()
        # Filter by programme type if requested
        programme_type = self.request.query_params.get('programme_type', None)
        if programme_type is not None:
            queryset = queryset.filter(programme_type=programme_type)
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset
