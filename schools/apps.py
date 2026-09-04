from django.apps import AppConfig


class SchoolsConfig(AppConfig):
    name = 'schools'

    def ready(self):
        # Registers HEIC/HEIF as a Pillow-openable format (iPhones save
        # photos in this format by default) -- needed both for the
        # LeftRightSheetUploadView's per-file image validation and for OCR
        # (vault.route_sheet_ocr.extract_text opens the file via
        # PIL.Image.open). Global to the whole process once registered
        # here, not just to this app, but this is the app that actually
        # accepts HEIC uploads (LeftRightSheetUpload).
        from pillow_heif import register_heif_opener
        register_heif_opener()
