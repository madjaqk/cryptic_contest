# Generated by Django 2.0 on 2018-04-02 09:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cryptics', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='contest',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='cryptics.Contest'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='submission',
            name='likers',
            field=models.ManyToManyField(related_name='clues_liked', to='cryptics.User'),
        ),
    ]
