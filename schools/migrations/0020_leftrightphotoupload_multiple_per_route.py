import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0019_leftrightphotoupload'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='leftrightphotoupload',
            name='unique_photo_upload_per_route_per_domain',
        ),
        migrations.RemoveField(
            model_name='leftrightphotoupload',
            name='updated_at',
        ),
        migrations.AddField(
            model_name='leftrightphotoupload',
            name='order',
            field=models.PositiveIntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AddField(
            model_name='leftrightphotoupload',
            name='uploaded_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, verbose_name='Uploaded'),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='leftrightphotoupload',
            options={'ordering': ['route_name', 'order', 'id'], 'verbose_name': 'Left & Right photo upload', 'verbose_name_plural': 'Left & Right photo uploads'},
        ),
    ]
