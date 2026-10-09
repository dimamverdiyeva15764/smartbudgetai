from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenRefreshView


def api_root(request):
    return JsonResponse({"message": "Smart Budget AI API is running successfully!"})


urlpatterns = [
    path('', api_root, name='api-root'),
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

# Return JSON (not Django's HTML pages) for errors outside DRF views.
handler404 = 'users.exceptions.json_not_found'
handler500 = 'users.exceptions.json_server_error'
