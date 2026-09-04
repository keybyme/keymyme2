import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0020_leftrightphotoupload_multiple_per_route'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='LeftRightPhotoUpload',
            new_name='LeftRightSheetUpload',
        ),
        migrations.RenameField(
            model_name='leftrightsheetupload',
            old_name='image',
            new_name='file',
        ),
        migrations.AlterField(
            model_name='leftrightsheetupload',
            name='file',
            field=models.FileField(
                upload_to='leftright_sheets/%Y/%m/',
                validators=[django.core.validators.FileExtensionValidator(allowed_extensions=[
                    'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'tif', 'heic', 'heif', 'pdf', 'docx',
                ])],
                verbose_name='File',
                help_text='A photo, PDF, or DOCX of one page of the sheet.',
            ),
        ),
        migrations.AlterField(
            model_name='leftrightsheetupload',
            name='domain',
            field=models.CharField(
                choices=[('mcps', 'MCPS'), ('transportation', 'Transportation')],
                default='mcps', max_length=20, verbose_name='Domain',
                help_text='Which module this upload belongs to — see LeftRight.domain.',
            ),
        ),
        migrations.AlterField(
            model_name='leftrightsheetupload',
            name='raw_text',
            field=models.TextField(blank=True, help_text='Raw extracted text, kept for troubleshooting a bad parse.'),
        ),
        migrations.AlterModelOptions(
            name='leftrightsheetupload',
            options={
                'ordering': ['route_name', 'order', 'id'],
                'verbose_name': 'Left & Right sheet upload',
                'verbose_name_plural': 'Left & Right sheet uploads',
            },
        ),
    ]
