# Generated by Django 5.0.4 on 2024-04-13 13:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_alter_category_category_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='category_image',
            field=models.ImageField(upload_to='catgories'),
        ),
    ]