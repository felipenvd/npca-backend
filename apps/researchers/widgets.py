from unfold.widgets import UnfoldAdminImageFieldWidget


class ResearcherPhotoWidget(UnfoldAdminImageFieldWidget):
    template_name = "admin/researchers/photo_widget.html"

    class Media:
        js = ("researchers/admin/photo_crop.js",)
        css = {"screen": ("researchers/admin/photo_crop.css",)}
