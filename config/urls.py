"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from accounts.views import SecureLoginView, SecureLogoutView
from kpis.views import home, landing, charts, dataset_data, performance_data

urlpatterns = [
    path("", landing, name="landing"),
    path("admin/", admin.site.urls),
    path("home/", home, name="home"),
    path("kpis/", charts, name="kpis_charts"),
    path("kpis/data/<int:dataset_id>/", dataset_data, name="kpis_dataset_data"),
    path("kpis/performance-data/<int:indicator_id>/", performance_data, name="kpis_performance_data"),
    path(
        "login/",
        SecureLoginView.as_view(),
        name="login",
    ),
    path("logout/", SecureLogoutView.as_view(), name="logout"),
    path("accounts/", include("accounts.urls")),
    path("schemas/", include("schemas.urls")),
    path("ingest/", include("ingest.urls")),
    path("validate/", include("validation.urls")),
    path("audit/", include("audit.urls")),
    path("performance/", include("performance.urls")),
    path("projects/", include("projects.urls")),
    path("structure/", include("structure.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
