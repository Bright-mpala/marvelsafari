from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('iso2', models.CharField(max_length=2, unique=True, verbose_name='ISO2 code')),
                ('iso3', models.CharField(blank=True, max_length=3, unique=True, verbose_name='ISO3 code')),
                ('name', models.CharField(max_length=200, verbose_name='country name')),
                ('official_name', models.CharField(blank=True, max_length=255, verbose_name='official name')),
                ('continent_code', models.CharField(blank=True, max_length=2, verbose_name='continent code')),
                ('currency_code', models.CharField(blank=True, max_length=3, verbose_name='currency code')),
                ('population', models.BigIntegerField(default=0, verbose_name='population')),
            ],
            options={
                'verbose_name': 'country',
                'verbose_name_plural': 'countries',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='City',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geoname_id', models.BigIntegerField(unique=True, verbose_name='GeoNames ID')),
                ('name', models.CharField(max_length=200, verbose_name='name')),
                ('ascii_name', models.CharField(blank=True, max_length=200, verbose_name='ASCII name')),
                ('admin1_code', models.CharField(blank=True, max_length=50, verbose_name='admin1 code')),
                ('admin1_name', models.CharField(blank=True, max_length=150, verbose_name='admin1 name')),
                ('admin2_code', models.CharField(blank=True, max_length=50, verbose_name='admin2 code')),
                ('admin2_name', models.CharField(blank=True, max_length=150, verbose_name='admin2 name')),
                ('latitude', models.DecimalField(decimal_places=6, max_digits=9, verbose_name='latitude')),
                ('longitude', models.DecimalField(decimal_places=6, max_digits=9, verbose_name='longitude')),
                ('timezone', models.CharField(blank=True, max_length=50, verbose_name='timezone')),
                ('population', models.BigIntegerField(default=0, verbose_name='population')),
                ('feature_class', models.CharField(blank=True, max_length=1, verbose_name='feature class')),
                ('feature_code', models.CharField(blank=True, max_length=10, verbose_name='feature code')),
                ('is_capital', models.BooleanField(default=False, verbose_name='capital city')),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cities', to='locations.country')),
            ],
            options={
                'verbose_name': 'city',
                'verbose_name_plural': 'cities',
                'ordering': ['name'],
            },
        ),
        migrations.AddIndex(
            model_name='city',
            index=models.Index(fields=['country', 'name'], name='locations_ci_country_5dc14c_idx'),
        ),
        migrations.AddIndex(
            model_name='city',
            index=models.Index(fields=['population'], name='locations_ci_populat_3f96c5_idx'),
        ),
        migrations.AddIndex(
            model_name='city',
            index=models.Index(fields=['timezone'], name='locations_ci_timezon_953f1c_idx'),
        ),
        migrations.AddIndex(
            model_name='city',
            index=models.Index(fields=['feature_code'], name='locations_ci_feature_00fbd5_idx'),
        ),
        migrations.AddIndex(
            model_name='country',
            index=models.Index(fields=['iso2'], name='locations_co_iso2_c044e0_idx'),
        ),
        migrations.AddIndex(
            model_name='country',
            index=models.Index(fields=['iso3'], name='locations_co_iso3_0ea5e7_idx'),
        ),
    ]
