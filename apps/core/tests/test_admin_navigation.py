from django.contrib import admin

from config.admin_navigation import sidebar_navigation


def test_labcompap_is_the_last_admin_sidebar_group(admin_client):
    response = admin_client.get("/admin/")
    request = response.wsgi_request

    navigation = sidebar_navigation(request)
    app_list = admin.site.get_app_list(request)

    assert response.status_code == 200
    assert len(navigation) == len(app_list)
    assert navigation[-2]["title"] == "Publicações"
    assert navigation[-1]["title"] == "LabCompAp"
