
import os
import json
from flask import Flask, request, session, g, current_app
from .config import Config
from .db import db
from .routes import main


translations = {}

def load_translations(app_instance):
    for lang_code in app_instance.config['LANGUAGES']:
        try:
            filepath = os.path.join(app_instance.root_path, 'static', 'translations', lang_code, 'strings.json')
            with open(filepath, 'r', encoding='utf-8') as f:
                translations[lang_code] = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Translation file not found for language '{lang_code}' at {filepath}")
            translations[lang_code] = {}
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in translation file for language '{lang_code}' at {filepath}")
            translations[lang_code] = {}

def get_text(text_key):
    """
    Retrieves the translation for a given text key based on the current locale.
    Falls back to Polish if translation not found or locale not set.
    """
    current_lang = session.get('lang', request.accept_languages.best_match(current_app.config['LANGUAGES']))
    if not current_lang or current_lang not in current_app.config['LANGUAGES']:
        current_lang = 'pl'
    return translations.get(current_lang, {}).get(text_key, translations.get('pl', {}).get(text_key, text_key))

def lang_code_to_display_name(lang_code):
    """Maps language codes to their full names for display."""
    name_map = {
        'en': 'English',
        'de': 'German',
        'es': 'Spanish',
        'pt': 'Portuguese',
        'cs': 'Czech',
        'da': 'Danish',
        'pl': 'Polish',
        'ja': 'Japanese',
        'sv': 'Swedish',
        'it': 'Italian',
        'tr': 'Turkish',
        'hr': 'Croatian',
        'he': 'Hebrew'
    }
    return name_map.get(lang_code, lang_code)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.jinja_env.add_extension('jinja2.ext.do')

    db.init_app(app)

    with app.app_context():
        load_translations(app)

    @app.before_request
    def before_request():
        if 'lang' in request.args:
            session['lang'] = request.args['lang']
        g.lang = session.get('lang', request.accept_languages.best_match(current_app.config['LANGUAGES']))
        if not g.lang or g.lang not in current_app.config['LANGUAGES']:
            g.lang = 'pl'

    @app.context_processor
    def inject_translation():
        return dict(_=get_text, lang_code_to_display_name=lang_code_to_display_name)

    app.register_blueprint(main)

    return app