from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0002_alter_transaccion_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='cuenta',
            name='numero',
            field=models.CharField(default='', max_length=50, verbose_name='Número de cuenta'),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='cuenta',
            name='tipo',
        ),
        migrations.AlterUniqueTogether(
            name='cuenta',
            unique_together={('owner', 'name'), ('owner', 'numero')},
        ),
    ]
