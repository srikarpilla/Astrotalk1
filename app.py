import logging
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import math
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz
import nltk
from nltk.tokenize import word_tokenize
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set NLTK data path
nltk.data.path.append(os.path.join(os.path.dirname(__file__), 'nltk_data'))
try:
    nltk.download('punkt', quiet=True)
except Exception as e:
    logger.error(f"Failed to download NLTK punkt: {str(e)}")

# Set ephemeris path
try:
    swe.set_ephe_path(os.path.join(os.path.dirname(__file__), 'ephe'))
    logger.debug("Ephemeris path set successfully")
except Exception as e:
    logger.error(f"Failed to set ephemeris path: {str(e)}")
    raise Exception("Ephemeris path './ephe' not found.")

app= Flask(__name__, static_folder='static')
CORS(application)

# [Rest of the code remains the same as in the previous optimized app.py]
# Sign mapper, horoscopes, user_data, geolocation_cache, spelling_corrections
# Routes: /, /process, /process_message
# (Copy the full code from the previous response, replacing 'app' with 'application')

signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
horoscopes = {
    'Aries': 'Your fiery spirit shines. Take bold steps today.',
    'Taurus': 'Ground yourself in patience. Build for the long term.',
    'Gemini': 'Your mind sparkles. Share your ideas freely.',
    'Cancer': 'Embrace your emotions. Nurture your loved ones.',
    'Leo': 'Your radiance leads. Inspire others with confidence.',
    'Virgo': 'Precision is your gift. Plan your next move carefully.',
    'Libra': 'Seek harmony in all. Balance brings peace.',
    'Scorpio': 'Dive deep into passions. Transformation awaits.',
    'Sagittarius': 'Adventure calls. Explore new horizons.',
    'Capricorn': 'Discipline drives success. Keep climbing.',
    'Aquarius': 'Innovate boldly. The future is yours.',
    'Pisces': 'Trust your dreams. Intuition guides you.'
}
user_data = {}
geolocation_cache = {}
last_geocode_time = 0
spelling_corrections = {
    'vishakapatanam': 'Visakhapatnam, India',
    'vizayanagaram': 'Vizianagaram, India',
    'vishakapatnam': 'Visakhapatnam, India',
    'vizianagram': 'Vizianagaram, India',
    'bombay': 'Mumbai, India'
}

@app.route('/')
def serve_index():
    return application.send_static_file('index.html')

@app.route('/process', methods=['POST'])
def process_birth_details():
    global last_geocode_time
    try:
        data = request.get_json()
        name = data['name']
        birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d')
        birth_time = datetime.strptime(data['birth_time'], '%H:%M')
        place = data['birth_place'].strip().lower()
        logger.debug(f"Processing birth details for {name}: {birth_date}, {birth_time}, {place}")

        corrected_place = spelling_corrections.get(place, place)
        if corrected_place != place:
            logger.debug(f"Corrected place name: {place} -> {corrected_place}")
            place = corrected_place

        if place in geolocation_cache:
            logger.debug(f"Using cached geolocation for {place}: {geolocation_cache[place]}")
            lat, lon = geolocation_cache[place]
        else:
            current_time = time.time()
            if current_time - last_geocode_time < 1:
                time.sleep(1 - (current_time - last_geocode_time))
            last_geocode_time = time.time()

            geolocator = Nominatim(user_agent='ai_astrologer', timeout=10)
            try:
                location = geolocator.geocode(place, exactly_one=True)
                if not location:
                    country = place.split(',')[-1].strip()
                    logger.debug(f"Falling back to country: {country}")
                    location = geolocator.geocode(country, exactly_one=True)
                    if not location:
                        logger.error(f"Geolocation failed for place: {place} and country: {country}")
                        return jsonify({'status': 'error', 'message': f'Invalid place: "{place}". Try a specific location like "Visakhapatnam, India" or check spelling.'})
                logger.debug(f"Geolocation result: {location.address}, Lat: {location.latitude}, Lon: {location.longitude}")
                lat = location.latitude
                lon = location.longitude
                geolocation_cache[place] = (lat, lon)
            except Exception as e:
                logger.error(f"Geolocation error: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Geolocation failed: {str(e)}. Try "Visakhapatnam, India" or check your internet connection.'})

        tf = TimezoneFinder()
        tz_str = tf.timezone_at(lng=lon, lat=lat)
        if not tz_str:
            logger.error(f"Timezone lookup failed for lat: {lat}, lon: {lon}")
            return jsonify({'status': 'error', 'message': 'Could not determine timezone'})

        tz = pytz.timezone(tz_str)
        birth_dt_local = datetime.combine(birth_date, birth_time.time())
        birth_dt_local = tz.localize(birth_dt_local)
        birth_dt_utc = birth_dt_local.astimezone(pytz.utc)

        try:
            jd = swe.utc_to_jd(birth_dt_utc.year, birth_dt_utc.month, birth_dt_utc.day,
                               birth_dt_utc.hour, birth_dt_utc.minute, birth_dt_utc.second, 1)[1]
        except Exception as e:
            logger.error(f"Julian date calculation failed: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Astrological calculation failed: {str(e)}'})

        try:
            sun_lon = swe.calc_ut(jd, swe.SUN)[0][0]
            moon_lon = swe.calc_ut(jd, swe.MOON)[0][0]
            asc = swe.houses(jd, lat, lon)[0][0]
        except Exception as e:
            logger.error(f"Planet position calculation failed: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Astrological calculation failed: {str(e)}'})

        def get_sign(lon):
            return signs[int(math.floor(lon / 30)) % 12]

        sun_sign = get_sign(sun_lon)
        moon_sign = get_sign(moon_lon)
        ascendant = get_sign(asc)

        user_data['name'] = name
        user_data['sun_sign'] = sun_sign
        user_data['moon_sign'] = moon_sign
        user_data['ascendant'] = ascendant
        user_data['birth_date'] = birth_date
        user_data['birth_time'] = birth_time

        trait_str = "Confidence: 0.80, Luck: 0.70, Creativity: 0.90, Health: 0.85, Love: 0.75"

        logger.debug(f"Success: Sun: {sun_sign}, Moon: {moon_sign}, Asc: {ascendant}, Traits: {trait_str}")
        return jsonify({
            'status': 'success',
            'sun_sign': sun_sign,
            'moon_sign': moon_sign,
            'ascendant': ascendant,
            'traits': trait_str
        })
    except Exception as e:
        logger.error(f"Unexpected error in /process: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Processing failed: {str(e)}'})

@app.route('/process_message', methods=['POST'])
def process_message():
    try:
        data = request.get_json()
        message = data['message'].lower()
        tokens = word_tokenize(message)
        logger.debug(f"Processing message: {message}")

        response = f"Namaste {user_data.get('name', 'User')}! "
        if 'horoscope' in tokens:
            response += f"Your daily horoscope: {horoscopes[user_data['sun_sign']]}"
        elif any(word in tokens for word in ['love', 'relationship', 'compatibility']):
            response += f"In love, your Moon in {user_data['moon_sign']} suggests emotional depth."
        elif any(word in tokens for word in ['career', 'job', 'work']):
            response += f"For career, your Sun in {user_data['sun_sign']} encourages bold moves."
        elif 'mangal' in tokens or 'dosha' in tokens:
            response += "Mangal Dosha analysis requires deeper chart analysis."
        elif 'remedies' in tokens:
            response += f"For balance, with Ascendant in {user_data['ascendant']}, try meditation."
        else:
            response += f"Your chart suggests optimism for {message}."

        logger.debug(f"Message response: {response}")
        return jsonify({'status': 'success', 'message': response})
    except Exception as e:
        logger.error(f"Error in /process_message: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':

    app.run(debug=True, host='0.0.0.0', port=5000)

