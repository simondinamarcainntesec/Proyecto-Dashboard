python manage.py collectstatic --noinput
sudo chown -R www-data:www-data staticfiles/
sudo chmod -R 755 staticfiles/

sudo systemctl restart apache2
