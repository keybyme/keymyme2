# Generated manually (schools.LeftRight has no rows yet — the create form
# has never successfully saved one — so there's no data to migrate).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0010_remove_ammidpmentry_latitude_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='leftright',
            name='unique_leftright_name_per_route',
        ),
        migrations.RemoveField(
            model_name='leftright',
            name='route',
        ),
        migrations.AddField(
            model_name='leftright',
            name='route_name',
            field=models.CharField(default='', max_length=100, verbose_name='Route'),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='leftright',
            options={'ordering': ['route_name', 'name'], 'verbose_name': 'Left & Right', 'verbose_name_plural': 'Lefts & Rights'},
        ),
        migrations.AddConstraint(
            model_name='leftright',
            constraint=models.UniqueConstraint(fields=('route_name', 'name'), name='unique_leftright_name_per_route'),
        ),
    ]
