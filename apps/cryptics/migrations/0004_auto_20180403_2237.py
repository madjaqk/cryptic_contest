# Generated by Django 2.0.4 on 2018-04-04 05:37

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cryptics', '0003_auto_20180403_0103'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='contest',
            name='started_by',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='contests_started', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
