from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0012_alter_locationcheckin_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='locationcheckin',
            name='check_date',
            field=models.DateField(verbose_name='Date'),
        ),
    ]
